from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import F, Q
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


def _missing_flow_error(target_type):
    mapping = {
        models.ApprovalFlow.TARGET_CONTRACT: '未配置启用的合同审批流程。',
        models.ApprovalFlow.TARGET_INVOICE: '未配置启用的开票审批流程。',
        models.ApprovalFlow.TARGET_QUOTE: '未配置启用的报价审批流程。',
    }
    return mapping.get(target_type, '未配置启用的审批流程。')


def _missing_flow_steps_error(target_type):
    mapping = {
        models.ApprovalFlow.TARGET_CONTRACT: '合同审批流程未配置节点，请先配置流程。',
        models.ApprovalFlow.TARGET_INVOICE: '开票审批流程未配置节点，请先配置流程。',
        models.ApprovalFlow.TARGET_QUOTE: '报价审批流程未配置节点，请先配置流程。',
    }
    return mapping.get(target_type, '审批流程未配置节点，请先配置流程。')


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
    region_id = getattr(region, 'id', None) if region is not None else None
    now = timezone.now()
    base_qs = models.ApprovalFlow.objects.filter(
        target_type=target_type,
        is_active=True,
        status=models.ApprovalFlow.STATUS_PUBLISHED,
    ).filter(
        Q(effective_from__isnull=True) | Q(effective_from__lte=now),
        Q(effective_to__isnull=True) | Q(effective_to__gte=now),
    )

    def ranked(qs):
        return qs.order_by('-priority', F('effective_from').desc(nulls_last=True), '-id').distinct()

    if region_id is not None:
        selected_scope_qs = ranked(
            base_qs.filter(scope_mode=models.ApprovalFlow.SCOPE_SELECTED_REGIONS, regions__id=region_id)
        )
        selected_flow = selected_scope_qs.first()
        if selected_flow:
            return selected_flow

        # Legacy compatibility: old single-region data before scope migration.
        legacy_region_flow = ranked(
            base_qs.filter(
                scope_mode=models.ApprovalFlow.SCOPE_SELECTED_REGIONS,
                regions__isnull=True,
                region_id=region_id,
            )
        ).first()
        if legacy_region_flow:
            return legacy_region_flow

        legacy_single_region_flow = ranked(base_qs.filter(region_id=region_id)).first()
        if legacy_single_region_flow:
            return legacy_single_region_flow

    all_regions_flow = ranked(
        base_qs.filter(
            Q(scope_mode=models.ApprovalFlow.SCOPE_ALL_REGIONS)
            | Q(scope_mode=models.ApprovalFlow.SCOPE_SELECTED_REGIONS, regions__isnull=True, region__isnull=True)
        )
    ).first()
    if all_regions_flow:
        return all_regions_flow

    return ranked(base_qs.filter(region__isnull=True)).first()


def _resolve_step_assignees(step, region):
    if (
        step.assignee_type == models.ApprovalStep.ASSIGNEE_TYPE_USER
        or (step.approver_user_id and not step.approver_role_id)
    ):
        if step.approver_user and step.approver_user.is_active:
            return [step.approver_user]
        return []

    if step.assignee_type == models.ApprovalStep.ASSIGNEE_TYPE_ROLE or step.approver_role_id:
        if step.approver_role:
            users_qs = core_models.User.objects.filter(
                Q(role=step.approver_role) | Q(roles=step.approver_role),
                is_active=True,
            ).distinct()
            if step.assignee_scope == models.ApprovalStep.ASSIGNEE_SCOPE_REGION:
                users_qs = users_qs.filter(region=region)
            return list(users_qs.order_by('id'))
        return []

    # Legacy compatibility before assignee_type was introduced.
    if step.approver_user and step.approver_user.is_active:
        return [step.approver_user]
    if step.approver_role:
        return list(
            core_models.User.objects.filter(
                Q(role=step.approver_role) | Q(roles=step.approver_role),
                region=region,
                is_active=True,
            ).distinct().order_by('id')
        )
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


def _is_admin_user(user):
    return bool(user and (user.is_superuser or user.is_staff))


def _build_todo_title(task, instance):
    target_type_label = {
        models.ApprovalFlow.TARGET_CONTRACT: '合同审批',
        models.ApprovalFlow.TARGET_INVOICE: '开票审批',
    }.get(instance.target_type, '审批')

    flow_name = ''
    step = getattr(task, 'step', None)
    if step:
        flow = getattr(step, 'flow', None)
        flow_name = (getattr(flow, 'name', '') or '').strip()

    if not flow_name and getattr(task, 'step_id', None):
        flow_name = (
            models.ApprovalStep.objects
            .filter(id=task.step_id)
            .values_list('flow__name', flat=True)
            .first() or ''
        ).strip()

    if not flow_name:
        flow_name = '审批流程'

    return f'{target_type_label} - {flow_name}'


def _schedule_task_create_todo(task, instance):
    todo.schedule_create_for_task(
        task=task,
        title=_build_todo_title(task, instance),
        content=f'请审批 {instance.target_type} #{instance.object_id}',
        url=todo.build_task_url(task.id),
        originator=instance.started_by,
    )


def _auto_skip_future_same_assignee_tasks(instance, source_task, actor):
    future_tasks = list(
        instance.tasks
        .select_related('step')
        .filter(
            assignee_id=source_task.assignee_id,
            step__order__gt=source_task.step.order,
            parent_task__isnull=True,
            status=models.ApprovalTask.STATUS_BLOCKED,
        )
        .order_by('step__order', 'id')
    )
    if not future_tasks:
        return

    now = timezone.now()
    for skipped_task in future_tasks:
        skipped_task.status = models.ApprovalTask.STATUS_APPROVED
        skipped_task.comment = '系统自动跳过（同一审批人）'
        skipped_task.decided_at = now
        skipped_task.save(update_fields=['status', 'comment', 'decided_at', 'updated_at'])
        _log_action(
            instance=instance,
            action=models.ApprovalActionLog.ACTION_APPROVED,
            actor=actor,
            task=skipped_task,
            from_status=models.ApprovalTask.STATUS_BLOCKED,
            to_status=models.ApprovalTask.STATUS_APPROVED,
            comment='系统自动跳过（同一审批人）',
            extra={'op': 'auto_skip_same_assignee'},
        )


def _log_auto_skip_no_assignee_step(instance, actor, step):
    _log_action(
        instance=instance,
        action=models.ApprovalActionLog.ACTION_APPROVED,
        actor=actor,
        from_status=models.ApprovalTask.STATUS_BLOCKED,
        to_status=models.ApprovalTask.STATUS_APPROVED,
        comment='系统自动跳过（未命中审批人）',
        extra={
            'op': 'auto_skip_no_assignee',
            'step_id': step.id,
            'step_order': step.order,
            'step_name': step.name or '',
        },
    )


def _advance_instance_after_current_step(instance, actor):
    current_order = instance.current_step
    while True:
        next_step_order = (
            instance.tasks
            .filter(step__order__gt=current_order)
            .order_by('step__order')
            .values_list('step__order', flat=True)
            .first()
        )
        if not next_step_order:
            target_obj = instance.content_object
            old_instance_status = instance.status
            instance.status = models.ApprovalInstance.STATUS_APPROVED
            instance.save(update_fields=['status', 'updated_at'])
            _log_action(
                instance=instance,
                action=models.ApprovalActionLog.ACTION_COMPLETED,
                actor=actor,
                from_status=old_instance_status,
                to_status=models.ApprovalInstance.STATUS_APPROVED,
            )
            _close_pending_tasks(instance, reason='流程已通过自动关闭')
            if target_obj:
                _sync_target_status(target_obj, models.ApprovalInstance.STATUS_APPROVED)
            return instance

        next_step_tasks = list(
            instance.tasks
            .select_related('step')
            .filter(step__order=next_step_order)
            .order_by('id')
        )
        blocked_ids = [item.id for item in next_step_tasks if item.status == models.ApprovalTask.STATUS_BLOCKED]
        pending_exists = any(item.status == models.ApprovalTask.STATUS_PENDING for item in next_step_tasks)

        if blocked_ids:
            models.ApprovalTask.objects.filter(id__in=blocked_ids).update(status=models.ApprovalTask.STATUS_PENDING)
            instance.current_step = next_step_order
            instance.save(update_fields=['current_step', 'updated_at'])
            activated_tasks = list(instance.tasks.filter(id__in=blocked_ids).select_related('step', 'assignee'))
            for next_task in activated_tasks:
                _schedule_task_create_todo(next_task, instance)
                _log_action(
                    instance=instance,
                    action=models.ApprovalActionLog.ACTION_TASK_ACTIVATED,
                    actor=actor,
                    task=next_task,
                    from_status=models.ApprovalTask.STATUS_BLOCKED,
                    to_status=models.ApprovalTask.STATUS_PENDING,
                )
            return instance

        if pending_exists:
            instance.current_step = next_step_order
            instance.save(update_fields=['current_step', 'updated_at'])
            return instance

        current_order = next_step_order


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
        raise ValueError(_missing_flow_error(target_type))
    steps = list(flow.steps.select_related('approver_role', 'approver_user').order_by('order', 'id'))
    if not steps:
        raise ValueError(_missing_flow_steps_error(target_type))

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

    tasks = []
    first_pending_order = None
    for step in steps:
        assignees = _resolve_step_assignees(step, region)
        if not assignees:
            _log_auto_skip_no_assignee_step(instance=instance, actor=user, step=step)
            continue
        if first_pending_order is None:
            first_pending_order = step.order
        for assignee in assignees:
            task_status = (
                models.ApprovalTask.STATUS_PENDING
                if step.order == first_pending_order
                else models.ApprovalTask.STATUS_BLOCKED
            )
            tasks.append(
                models.ApprovalTask(
                    instance=instance,
                    step=step,
                    assignee=assignee,
                    status=task_status,
                )
            )

    if not tasks:
        old_instance_status = instance.status
        instance.current_step = steps[-1].order
        instance.status = models.ApprovalInstance.STATUS_APPROVED
        instance.save(update_fields=['current_step', 'status', 'updated_at'])
        _log_action(
            instance=instance,
            action=models.ApprovalActionLog.ACTION_COMPLETED,
            actor=user,
            from_status=old_instance_status,
            to_status=models.ApprovalInstance.STATUS_APPROVED,
            comment='流程无可用审批人节点，系统自动通过',
            extra={'op': 'auto_skip_no_assignee_all'},
        )
        _sync_target_status(target_obj, models.ApprovalInstance.STATUS_APPROVED)
        return instance

    if instance.current_step != first_pending_order:
        instance.current_step = first_pending_order
        instance.save(update_fields=['current_step', 'updated_at'])

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
    if task.parent_task_id and not approved:
        raise ValueError('加签任务仅支持提交意见，不可驳回流程')
    if not task.parent_task_id:
        has_pending_add_sign = models.ApprovalTask.objects.filter(
            parent_task_id=task.id,
            status=models.ApprovalTask.STATUS_PENDING,
        ).exists()
        if has_pending_add_sign:
            raise ValueError('加签处理中，原任务不可处理')

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

    if task.parent_task_id:
        parent_task = task.parent_task
        if parent_task and parent_task.status == models.ApprovalTask.STATUS_BLOCKED:
            old_parent_status = parent_task.status
            parent_task.status = models.ApprovalTask.STATUS_PENDING
            parent_task.save(update_fields=['status', 'updated_at'])
            _schedule_task_create_todo(parent_task, instance)
            _log_action(
                instance=instance,
                action=models.ApprovalActionLog.ACTION_TASK_ACTIVATED,
                actor=user,
                task=parent_task,
                from_status=old_parent_status,
                to_status=models.ApprovalTask.STATUS_PENDING,
                comment='加签完成，返回原审批人',
                extra={'op': 'add_sign_resume', 'from_task_id': task.id},
            )
        return instance

    step_order = task.step.order
    step_still_pending = instance.tasks.filter(
        step__order=step_order,
        status=models.ApprovalTask.STATUS_PENDING,
    ).exists()
    if step_still_pending:
        return instance

    _auto_skip_future_same_assignee_tasks(instance, task, actor=user)
    return _advance_instance_after_current_step(instance, actor=user)


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
    if task.assignee_id != user.id and not _is_admin_user(user):
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
        parent_task=task.parent_task,
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
    if task.assignee_id != user.id and not _is_admin_user(user):
        raise PermissionError('Not allowed to add sign on this task')
    if task.parent_task_id:
        raise ValueError('加签任务不支持再次加签')
    has_pending_add_sign = models.ApprovalTask.objects.filter(
        parent_task_id=task.id,
        status=models.ApprovalTask.STATUS_PENDING,
    ).exists()
    if has_pending_add_sign:
        raise ValueError('当前任务已有进行中的加签')
    if task.status != models.ApprovalTask.STATUS_PENDING:
        raise ValueError('Task is not pending')
    if not new_assignee or not new_assignee.is_active:
        raise ValueError('Target assignee is invalid')
    if task.assignee_id == new_assignee.id:
        raise ValueError('Target assignee must be different')
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

    old_task_status = task.status
    task.status = models.ApprovalTask.STATUS_BLOCKED
    task.comment = comment or f'加签给 {new_assignee.username}'
    task.decided_at = None
    task.save(update_fields=['status', 'comment', 'decided_at', 'updated_at'])
    todo.schedule_complete_for_task(task, reason='任务加签挂起')

    new_task = models.ApprovalTask.objects.create(
        instance=task.instance,
        step=task.step,
        assignee=new_assignee,
        parent_task=task,
        status=models.ApprovalTask.STATUS_PENDING,
    )
    _schedule_task_create_todo(new_task, task.instance)
    _log_action(
        instance=task.instance,
        action=models.ApprovalActionLog.ACTION_TASK_ACTIVATED,
        actor=user,
        task=task,
        from_status=old_task_status,
        to_status=models.ApprovalTask.STATUS_BLOCKED,
        comment='发起加签，原任务挂起',
        extra={'op': 'add_sign_suspend', 'to_assignee_id': new_assignee.id},
    )
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
            'parent_task_id': task.parent_task_id,
            'task_kind': 'add_sign' if task.parent_task_id else 'normal',
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
            'parent_task_id': task.parent_task_id,
            'task_kind': 'add_sign' if task.parent_task_id else 'normal',
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

    pending_approvers = []
    approver_seen_ids = set()
    step_groups = {}
    current_step_name = ''
    for task in tasks:
        step_order = task.get('step_order') or 0
        if step_order not in step_groups:
            step_groups[step_order] = {
                'step_order': step_order,
                'step_name': task.get('step_name') or '',
                'total_count': 0,
                'approved_count': 0,
                'rejected_count': 0,
                'pending_count': 0,
                'blocked_count': 0,
                'canceled_count': 0,
                'status': 'waiting',
            }
        group = step_groups[step_order]
        group['total_count'] += 1
        task_status = task.get('status')
        if task_status == models.ApprovalTask.STATUS_APPROVED:
            group['approved_count'] += 1
        elif task_status == models.ApprovalTask.STATUS_REJECTED:
            group['rejected_count'] += 1
        elif task_status == models.ApprovalTask.STATUS_PENDING:
            group['pending_count'] += 1
            assignee_id = task.get('assignee')
            if assignee_id not in approver_seen_ids:
                approver_seen_ids.add(assignee_id)
                pending_approvers.append({
                    'id': assignee_id,
                    'username': task.get('assignee_name') or '',
                })
        elif task_status == models.ApprovalTask.STATUS_BLOCKED:
            group['blocked_count'] += 1
        elif task_status == models.ApprovalTask.STATUS_CANCELED:
            group['canceled_count'] += 1

        if step_order == instance.current_step and not current_step_name:
            current_step_name = task.get('step_name') or ''

    ordered_step_groups = []
    for step_order in sorted(step_groups.keys()):
        group = step_groups[step_order]
        if group['pending_count'] > 0:
            group['status'] = 'active'
        elif group['rejected_count'] > 0:
            group['status'] = 'rejected'
        elif group['approved_count'] == group['total_count'] and group['total_count'] > 0:
            group['status'] = 'done'
        elif group['blocked_count'] == group['total_count'] and group['total_count'] > 0:
            group['status'] = 'waiting'
        elif group['canceled_count'] == group['total_count'] and group['total_count'] > 0:
            group['status'] = 'canceled'
        else:
            group['status'] = 'done'
        ordered_step_groups.append(group)

    latest_action = logs[-1] if logs else None

    return {
        'instance': {
            'id': instance.id,
            'status': instance.status,
            'current_step': instance.current_step,
            'current_step_name': current_step_name,
            'started_by': instance.started_by_id,
            'started_by_name': getattr(instance.started_by, 'username', ''),
            'target_type': instance.target_type,
            'target_id': instance.object_id,
            'created_at': instance.created_at,
            'updated_at': instance.updated_at,
            'pending_approvers': pending_approvers,
            'latest_action': latest_action,
        },
        'target': target_data,
        'step_groups': ordered_step_groups,
        'tasks': tasks,
        'logs': logs,
    }


def _pick_progress_instance(target_obj):
    content_type = ContentType.objects.get_for_model(target_obj.__class__)
    adapter = registry.get_adapter_for_obj(target_obj)
    target_type = adapter.get_target_type() if adapter else ''

    queryset = models.ApprovalInstance.objects.filter(
        content_type=content_type,
        object_id=target_obj.id,
    )
    if target_type:
        queryset = queryset.filter(target_type=target_type)

    pending_instance = queryset.filter(
        status=models.ApprovalInstance.STATUS_PENDING
    ).order_by('-created_at', '-id').first()
    if pending_instance:
        return pending_instance
    return queryset.order_by('-created_at', '-id').first()


def _serialize_instance_progress(instance):
    tasks = list(instance.tasks.select_related('step', 'assignee').order_by('step__order', 'id'))
    current_step_name = ''
    for task in tasks:
        if task.step and task.step.order == instance.current_step:
            current_step_name = task.step.name or ''
            break

    pending_approvers = []
    seen_approver_ids = set()
    for task in tasks:
        if task.status != models.ApprovalTask.STATUS_PENDING:
            continue
        if task.assignee_id in seen_approver_ids:
            continue
        seen_approver_ids.add(task.assignee_id)
        pending_approvers.append({
            'id': task.assignee_id,
            'username': getattr(task.assignee, 'username', ''),
        })

    latest_action_obj = instance.action_logs.select_related('actor').order_by('-created_at', '-id').first()
    latest_action = None
    if latest_action_obj:
        latest_action = {
            'action': latest_action_obj.action,
            'actor_name': getattr(latest_action_obj.actor, 'username', ''),
            'comment': latest_action_obj.comment,
            'created_at': latest_action_obj.created_at,
        }

    return {
        'has_instance': True,
        'instance_id': instance.id,
        'instance_status': instance.status,
        'current_step': instance.current_step,
        'current_step_name': current_step_name,
        'pending_approvers': pending_approvers,
        'started_by_name': getattr(instance.started_by, 'username', ''),
        'created_at': instance.created_at,
        'updated_at': instance.updated_at,
        'latest_action': latest_action,
    }


def get_target_approval_progress(target_obj):
    instance = _pick_progress_instance(target_obj)
    if not instance:
        return {
            'has_instance': False,
            'instance_id': None,
            'instance_status': None,
            'current_step': None,
            'current_step_name': '',
            'pending_approvers': [],
            'started_by_name': '',
            'created_at': None,
            'updated_at': None,
            'latest_action': None,
        }
    return _serialize_instance_progress(instance)
