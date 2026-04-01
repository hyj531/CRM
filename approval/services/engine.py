from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from approval import models
from approval.adapters import registry
from approval.services import todo
from core import models as core_models


def _resolve_target_type(target_obj):
    adapter = registry.get_adapter_for_obj(target_obj)
    if not adapter:
        raise ValueError('Unsupported target type')
    return adapter.get_target_type()


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


@transaction.atomic
def start_approval(target_obj, user):
    adapter = registry.get_adapter_for_obj(target_obj)
    if not adapter:
        raise ValueError('Unsupported target type')
    target_type = adapter.get_target_type()
    flow = get_flow_for_region(target_type, adapter.get_region(target_obj))
    if not flow:
        flow = _get_or_create_admin_flow(target_type)

    content_type = ContentType.objects.get_for_model(target_obj.__class__)
    instance = models.ApprovalInstance.objects.create(
        content_type=content_type,
        object_id=target_obj.id,
        target_type=target_type,
        region=adapter.get_region(target_obj),
        started_by=user,
        current_step=1,
    )

    _sync_target_status(target_obj, models.ApprovalInstance.STATUS_PENDING)

    steps = list(flow.steps.all())
    if not steps:
        instance.status = models.ApprovalInstance.STATUS_APPROVED
        instance.save(update_fields=['status'])
        _sync_target_status(target_obj, models.ApprovalInstance.STATUS_APPROVED)
        return instance

    tasks = []
    for index, step in enumerate(steps, start=1):
        assignees = _resolve_step_assignees(step, adapter.get_region(target_obj))
        if not assignees:
            raise ValueError('Approval flow has a step without assignees')
        for assignee in assignees:
            status = models.ApprovalTask.STATUS_PENDING if index == 1 else models.ApprovalTask.STATUS_BLOCKED
            tasks.append(
                models.ApprovalTask(
                    instance=instance,
                    step=step,
                    assignee=assignee,
                    status=status,
                )
            )
    if tasks:
        models.ApprovalTask.objects.bulk_create(tasks)
        for task in instance.tasks.filter(status=models.ApprovalTask.STATUS_PENDING):
            todo.send_todo_task(
                task.assignee,
                title='审批待办提醒',
                content=f'请审批 {target_type} #{target_obj.id}',
                url=todo.build_task_url(task.id),
                source_id=f'approval-task-{task.id}',
                originator=instance.started_by,
            )

    return instance


@transaction.atomic
def approve_task(task, user, approved, comment=''):
    if task.assignee_id != user.id and not user.is_superuser:
        raise PermissionError('Not allowed to approve this task')

    if task.status not in [models.ApprovalTask.STATUS_PENDING]:
        raise ValueError('Task is not pending')

    task.status = models.ApprovalTask.STATUS_APPROVED if approved else models.ApprovalTask.STATUS_REJECTED
    task.comment = comment or ''
    task.decided_at = timezone.now()
    task.save(update_fields=['status', 'comment', 'decided_at'])

    instance = task.instance
    target_obj = instance.content_object

    if not approved:
        instance.status = models.ApprovalInstance.STATUS_REJECTED
        instance.save(update_fields=['status'])
        if target_obj:
            _sync_target_status(target_obj, models.ApprovalInstance.STATUS_REJECTED)
        return instance

    step_order = task.step.order
    if instance.tasks.filter(step__order=step_order, status=models.ApprovalTask.STATUS_PENDING).exists():
        return instance
    next_step = instance.tasks.filter(step__order=step_order + 1)
    if next_step.exists():
        next_step.update(status=models.ApprovalTask.STATUS_PENDING)
        instance.current_step = step_order + 1
        instance.save(update_fields=['current_step'])
        for task_item in next_step:
            todo.send_todo_task(
                task_item.assignee,
                title='审批待办提醒',
                content=f'请审批 {instance.target_type} #{instance.object_id}',
                url=todo.build_task_url(task_item.id),
                source_id=f'approval-task-{task_item.id}',
                originator=instance.started_by,
            )
        return instance

    instance.status = models.ApprovalInstance.STATUS_APPROVED
    instance.save(update_fields=['status'])
    if target_obj:
        _sync_target_status(target_obj, models.ApprovalInstance.STATUS_APPROVED)
    return instance


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
