from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from approval import models
from approval.adapters import registry
from approval.services import todo
from core import models as core_models
from core.services import approval_switches


def _resolve_target_type(target_obj):
    adapter = registry.get_adapter_for_obj(target_obj)
    if not adapter:
        raise ValueError('Unsupported target type')
    return adapter.get_target_type()


def _log_action(instance, action, actor=None, task=None, from_status='', to_status='', comment='', extra=None):
    models.ApprovalActionLog.objects.create(
        instance=instance,
        task=task,
        actor=actor,
        action=action,
        from_status=from_status or '',
        to_status=to_status or '',
        comment=comment or '',
        extra=extra or {},
    )


def get_flow_for_region(target_type, region):
    flow = (
        models.ApprovalFlow.objects
        .filter(target_type=target_type, is_active=True, region=region)
        .order_by('-id')
        .first()
    )
    if flow:
        return flow
    return (
        models.ApprovalFlow.objects
        .filter(target_type=target_type, is_active=True, region__isnull=True)
        .order_by('-id')
        .first()
    )


def _get_fallback_admin_user():
    return core_models.User.objects.filter(is_superuser=True, is_active=True).order_by('id').first()


def _get_or_create_admin_flow(target_type):
    admin_user = _get_fallback_admin_user()
    if not admin_user:
        raise ValueError('No active approval flow configured, and no superuser available')

    flow = (
        models.ApprovalFlow.objects
        .filter(target_type=target_type, is_active=True, region__isnull=True, name='系统默认审批流程')
        .order_by('-id')
        .first()
    )
    if not flow:
        flow = models.ApprovalFlow.objects.create(
            name='系统默认审批流程',
            target_type=target_type,
            region=None,
            is_active=True,
        )
    if not flow.steps.exists():
        models.ApprovalStep.objects.create(
            flow=flow,
            order=1,
            name='超级管理员审批',
            approver_user=admin_user,
        )
    return flow


def _resolve_step_assignees(step, region):
    if step.approver_user:
        return [step.approver_user]
    if step.approver_role:
        return list(core_models.User.objects.filter(role=step.approver_role, region=region, is_active=True))
    return []


def _sync_target_status(target_obj, status):
    adapter = registry.get_adapter_for_obj(target_obj)
    if not adapter:
        return
    adapter.set_approval_status(target_obj, status)


def _ensure_approval_switch_enabled(target_type):
    if target_type == models.ApprovalFlow.TARGET_CONTRACT and not approval_switches.is_contract_approval_enabled():
        raise ValueError('合同审批未启用。')
    if target_type == models.ApprovalFlow.TARGET_INVOICE and not approval_switches.is_invoice_approval_enabled():
        raise ValueError('开票审批未启用。')


def _schedule_task_create_todo(task, instance):
    todo.schedule_create_for_task(
        task=task,
        title='审批待办提醒',
        content=f'请审批 {instance.target_type} #{instance.object_id}',
        url=todo.build_task_url(task.id),
        originator=instance.started_by,
    )


def _close_pending_tasks(instance, reason, exclude_task_ids=None):
    if exclude_task_ids is None:
        exclude_task_ids = []
    now = timezone.now()
    pending_qs = instance.tasks.filter(status=models.ApprovalTask.STATUS_PENDING).exclude(id__in=exclude_task_ids)
    for pending_task in pending_qs:
        pending_task.status = models.ApprovalTask.STATUS_CANCELED
        pending_task.comment = reason
        pending_task.decided_at = now
        pending_task.save(update_fields=['status', 'comment', 'decided_at', 'updated_at'])
        todo.schedule_complete_for_task(pending_task, reason=reason)
        _log_action(
            instance=instance,
            action=models.ApprovalActionLog.ACTION_COMPLETED,
            actor=pending_task.assignee,
            task=pending_task,
            from_status=models.ApprovalTask.STATUS_PENDING,
            to_status=models.ApprovalTask.STATUS_CANCELED,
            comment=reason,
        )


@transaction.atomic
def start_approval(target_obj, user):
    adapter = registry.get_adapter_for_obj(target_obj)
    if not adapter:
        raise ValueError('Unsupported target type')
    target_type = adapter.get_target_type()
    _ensure_approval_switch_enabled(target_type)
    region = adapter.get_region(target_obj)

    flow = get_flow_for_region(target_type, region)
    if not flow:
        flow = _get_or_create_admin_flow(target_type)

    content_type = ContentType.objects.get_for_model(target_obj.__class__)
    pending_exists = models.ApprovalInstance.objects.filter(
        content_type=content_type,
        object_id=target_obj.id,
        status=models.ApprovalInstance.STATUS_PENDING,
    ).exists()
    if pending_exists:
        raise ValueError('An approval instance is already pending for this target')

    instance = models.ApprovalInstance.objects.create(
        content_type=content_type,
        object_id=target_obj.id,
        target_type=target_type,
        region=region,
        status=models.ApprovalInstance.STATUS_PENDING,
        started_by=user,
        current_step=1,
    )
    _log_action(
        instance=instance,
        action=models.ApprovalActionLog.ACTION_SUBMITTED,
        actor=user,
        from_status='',
        to_status=models.ApprovalInstance.STATUS_PENDING,
    )

    _sync_target_status(target_obj, models.ApprovalInstance.STATUS_PENDING)

    steps = list(flow.steps.all())
    if not steps:
        old_status = instance.status
        instance.status = models.ApprovalInstance.STATUS_APPROVED
        instance.save(update_fields=['status', 'updated_at'])
        _sync_target_status(target_obj, models.ApprovalInstance.STATUS_APPROVED)
        _log_action(
            instance=instance,
            action=models.ApprovalActionLog.ACTION_COMPLETED,
            actor=user,
            from_status=old_status,
            to_status=models.ApprovalInstance.STATUS_APPROVED,
        )
        return instance

    tasks = []
    for index, step in enumerate(steps, start=1):
        assignees = _resolve_step_assignees(step, region)
        if not assignees:
            raise ValueError('Approval flow has a step without assignees')
        for assignee in assignees:
            task_status = models.ApprovalTask.STATUS_PENDING if index == 1 else models.ApprovalTask.STATUS_BLOCKED
            tasks.append(
                models.ApprovalTask(
                    instance=instance,
                    step=step,
                    assignee=assignee,
                    status=task_status,
                )
            )
    if tasks:
        models.ApprovalTask.objects.bulk_create(tasks)
        first_step_tasks = list(instance.tasks.filter(status=models.ApprovalTask.STATUS_PENDING))
        for pending_task in first_step_tasks:
            _schedule_task_create_todo(pending_task, instance)
            _log_action(
                instance=instance,
                action=models.ApprovalActionLog.ACTION_TASK_ACTIVATED,
                actor=user,
                task=pending_task,
                from_status=models.ApprovalTask.STATUS_BLOCKED,
                to_status=models.ApprovalTask.STATUS_PENDING,
            )

    return instance


@transaction.atomic
def approve_task(task, user, approved, comment=''):
    if task.assignee_id != user.id and not user.is_superuser:
        raise PermissionError('Not allowed to approve this task')
    if task.status != models.ApprovalTask.STATUS_PENDING:
        raise ValueError('Task is not pending')

    old_task_status = task.status
    task.status = models.ApprovalTask.STATUS_APPROVED if approved else models.ApprovalTask.STATUS_REJECTED
    task.comment = comment or ''
    task.decided_at = timezone.now()
    task.save(update_fields=['status', 'comment', 'decided_at', 'updated_at'])
    todo.schedule_complete_for_task(task, reason='任务已处理')

    instance = task.instance
    target_obj = instance.content_object
    _log_action(
        instance=instance,
        action=models.ApprovalActionLog.ACTION_APPROVED if approved else models.ApprovalActionLog.ACTION_REJECTED,
        actor=user,
        task=task,
        from_status=old_task_status,
        to_status=task.status,
        comment=comment or '',
    )

    if not approved:
        old_instance_status = instance.status
        instance.status = models.ApprovalInstance.STATUS_REJECTED
        instance.save(update_fields=['status', 'updated_at'])
        _log_action(
            instance=instance,
            action=models.ApprovalActionLog.ACTION_REJECTED,
            actor=user,
            from_status=old_instance_status,
            to_status=models.ApprovalInstance.STATUS_REJECTED,
            comment=comment or '',
        )
        _close_pending_tasks(instance, reason='流程已驳回自动关闭', exclude_task_ids=[task.id])
        if target_obj:
            _sync_target_status(target_obj, models.ApprovalInstance.STATUS_REJECTED)
        return instance

    step_order = task.step.order
    step_still_pending = instance.tasks.filter(
        step__order=step_order,
        status=models.ApprovalTask.STATUS_PENDING,
    ).exists()
    if step_still_pending:
        return instance

    next_step_tasks = list(instance.tasks.filter(step__order=step_order + 1))
    if next_step_tasks:
        models.ApprovalTask.objects.filter(id__in=[item.id for item in next_step_tasks]).update(
            status=models.ApprovalTask.STATUS_PENDING
        )
        instance.current_step = step_order + 1
        instance.save(update_fields=['current_step', 'updated_at'])
        refreshed_next_tasks = list(instance.tasks.filter(id__in=[item.id for item in next_step_tasks]))
        for next_task in refreshed_next_tasks:
            _schedule_task_create_todo(next_task, instance)
            _log_action(
                instance=instance,
                action=models.ApprovalActionLog.ACTION_TASK_ACTIVATED,
                actor=user,
                task=next_task,
                from_status=models.ApprovalTask.STATUS_BLOCKED,
                to_status=models.ApprovalTask.STATUS_PENDING,
            )
        return instance

    old_instance_status = instance.status
    instance.status = models.ApprovalInstance.STATUS_APPROVED
    instance.save(update_fields=['status', 'updated_at'])
    _log_action(
        instance=instance,
        action=models.ApprovalActionLog.ACTION_COMPLETED,
        actor=user,
        from_status=old_instance_status,
        to_status=models.ApprovalInstance.STATUS_APPROVED,
    )
    _close_pending_tasks(instance, reason='流程已通过自动关闭')
    if target_obj:
        _sync_target_status(target_obj, models.ApprovalInstance.STATUS_APPROVED)
    return instance


@transaction.atomic
def withdraw_approval(instance, user, comment=''):
    if instance.started_by_id != user.id and not user.is_superuser:
        raise PermissionError('Not allowed to withdraw this approval')
    if instance.status != models.ApprovalInstance.STATUS_PENDING:
        raise ValueError('Only pending approval can be withdrawn')

    old_status = instance.status
    instance.status = models.ApprovalInstance.STATUS_WITHDRAWN
    instance.save(update_fields=['status', 'updated_at'])
    _close_pending_tasks(instance, reason='流程已撤回自动关闭')
    _log_action(
        instance=instance,
        action=models.ApprovalActionLog.ACTION_WITHDRAWN,
        actor=user,
        from_status=old_status,
        to_status=models.ApprovalInstance.STATUS_WITHDRAWN,
        comment=comment or '',
    )

    target_obj = instance.content_object
    if target_obj:
        _sync_target_status(target_obj, models.ApprovalInstance.STATUS_WITHDRAWN)
    return instance


@transaction.atomic
def transfer_task(task, user, new_assignee, comment=''):
    if task.assignee_id != user.id and not user.is_superuser:
        raise PermissionError('Not allowed to transfer this task')
    if task.status != models.ApprovalTask.STATUS_PENDING:
        raise ValueError('Task is not pending')
    if not new_assignee or not new_assignee.is_active:
        raise ValueError('Target assignee is invalid')
    if task.assignee_id == new_assignee.id:
        raise ValueError('Target assignee must be different')
    if task.instance.status != models.ApprovalInstance.STATUS_PENDING:
        raise ValueError('Approval instance is not pending')

    old_assignee_id = task.assignee_id
    task.status = models.ApprovalTask.STATUS_CANCELED
    task.comment = comment or f'转交给 {new_assignee.username}'
    task.decided_at = timezone.now()
    task.save(update_fields=['status', 'comment', 'decided_at', 'updated_at'])
    todo.schedule_complete_for_task(task, reason='任务转交后关闭')

    new_task = models.ApprovalTask.objects.create(
        instance=task.instance,
        step=task.step,
        assignee=new_assignee,
        status=models.ApprovalTask.STATUS_PENDING,
    )
    _schedule_task_create_todo(new_task, task.instance)
    _log_action(
        instance=task.instance,
        action=models.ApprovalActionLog.ACTION_TASK_ACTIVATED,
        actor=user,
        task=new_task,
        from_status=models.ApprovalTask.STATUS_BLOCKED,
        to_status=models.ApprovalTask.STATUS_PENDING,
        comment='任务转交',
        extra={'op': 'transfer', 'from_assignee_id': old_assignee_id, 'to_assignee_id': new_assignee.id},
    )
    return new_task


@transaction.atomic
def add_sign_task(task, user, new_assignee, comment=''):
    if task.assignee_id != user.id and not user.is_superuser:
        raise PermissionError('Not allowed to add sign on this task')
    if task.status != models.ApprovalTask.STATUS_PENDING:
        raise ValueError('Task is not pending')
    if not new_assignee or not new_assignee.is_active:
        raise ValueError('Target assignee is invalid')
    if task.instance.status != models.ApprovalInstance.STATUS_PENDING:
        raise ValueError('Approval instance is not pending')

    exists = models.ApprovalTask.objects.filter(
        instance=task.instance,
        step=task.step,
        assignee=new_assignee,
        status=models.ApprovalTask.STATUS_PENDING,
    ).exists()
    if exists:
        raise ValueError('Assignee already has pending task on this step')

    new_task = models.ApprovalTask.objects.create(
        instance=task.instance,
        step=task.step,
        assignee=new_assignee,
        status=models.ApprovalTask.STATUS_PENDING,
    )
    _schedule_task_create_todo(new_task, task.instance)
    _log_action(
        instance=task.instance,
        action=models.ApprovalActionLog.ACTION_TASK_ACTIVATED,
        actor=user,
        task=new_task,
        from_status=models.ApprovalTask.STATUS_BLOCKED,
        to_status=models.ApprovalTask.STATUS_PENDING,
        comment=comment or '任务加签',
        extra={'op': 'add_sign', 'to_assignee_id': new_assignee.id},
    )
    return new_task


def get_task_detail(task, request=None):
    instance = task.instance
    target_obj = instance.content_object
    adapter = registry.get_adapter_for_type(instance.target_type)
    target_data = {
        'type': instance.target_type,
        'id': instance.object_id,
        'title': '',
        'fields': [],
        'attachments': [],
    }
    if adapter and target_obj:
        target_data['title'] = adapter.get_title(target_obj)
        target_data['fields'] = adapter.get_display_fields(target_obj)
        target_data['attachments'] = adapter.get_attachments(target_obj, request=request)

    return {
        'task': {
            'id': task.id,
            'status': task.status,
            'comment': task.comment,
            'decided_at': task.decided_at,
            'assignee': task.assignee_id,
            'assignee_name': getattr(task.assignee, 'username', ''),
            'step_name': task.step.name if task.step else '',
            'step_order': task.step.order if task.step else None,
            'todo_status': task.todo_status,
            'todo_channel': task.todo_channel,
            'todo_source_id': task.todo_source_id,
            'todo_task_id': task.todo_task_id,
            'todo_last_error': task.todo_last_error,
        },
        'instance': {
            'id': instance.id,
            'status': instance.status,
            'current_step': instance.current_step,
            'started_by': instance.started_by_id,
            'started_by_name': getattr(instance.started_by, 'username', ''),
            'target_type': instance.target_type,
            'created_at': instance.created_at,
        },
        'target': target_data,
    }


def get_instance_detail(instance, request=None):
    target_obj = instance.content_object
    adapter = registry.get_adapter_for_type(instance.target_type)
    target_data = {
        'type': instance.target_type,
        'id': instance.object_id,
        'title': '',
        'fields': [],
        'attachments': [],
    }
    if adapter and target_obj:
        target_data['title'] = adapter.get_title(target_obj)
        target_data['fields'] = adapter.get_display_fields(target_obj)
        target_data['attachments'] = adapter.get_attachments(target_obj, request=request)

    tasks = []
    for task in instance.tasks.select_related('step', 'assignee').order_by('step__order', 'id'):
        tasks.append({
            'id': task.id,
            'step_order': task.step.order if task.step else None,
            'step_name': task.step.name if task.step else '',
            'assignee': task.assignee_id,
            'assignee_name': getattr(task.assignee, 'username', ''),
            'status': task.status,
            'comment': task.comment,
            'decided_at': task.decided_at,
            'todo_status': task.todo_status,
            'todo_channel': task.todo_channel,
            'todo_source_id': task.todo_source_id,
            'todo_task_id': task.todo_task_id,
            'todo_last_error': task.todo_last_error,
            'todo_retry_count': task.todo_retry_count,
            'todo_next_retry_at': task.todo_next_retry_at,
        })

    logs = []
    for log in instance.action_logs.select_related('actor', 'task').order_by('created_at', 'id'):
        logs.append({
            'id': log.id,
            'action': log.action,
            'from_status': log.from_status,
            'to_status': log.to_status,
            'comment': log.comment,
            'actor': log.actor_id,
            'actor_name': getattr(log.actor, 'username', ''),
            'task_id': log.task_id,
            'extra': log.extra or {},
            'created_at': log.created_at,
        })

    return {
        'instance': {
            'id': instance.id,
            'status': instance.status,
            'current_step': instance.current_step,
            'started_by': instance.started_by_id,
            'started_by_name': getattr(instance.started_by, 'username', ''),
            'target_type': instance.target_type,
            'target_id': instance.object_id,
            'created_at': instance.created_at,
            'updated_at': instance.updated_at,
        },
        'target': target_data,
        'tasks': tasks,
        'logs': logs,
    }
