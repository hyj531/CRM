from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core import models
from core.services import dingtalk


def _resolve_target_type(target_obj):
    if isinstance(target_obj, models.Quote):
        return models.ApprovalFlow.TARGET_QUOTE
    if isinstance(target_obj, models.Contract):
        return models.ApprovalFlow.TARGET_CONTRACT
    if isinstance(target_obj, models.Invoice):
        return models.ApprovalFlow.TARGET_INVOICE
    raise ValueError('Unsupported target type')


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


def _resolve_step_assignees(step, region):
    if step.approver_user:
        return [step.approver_user]
    if step.approver_role:
        return list(
            models.User.objects.filter(
                Q(role=step.approver_role) | Q(roles=step.approver_role),
                region=region,
                is_active=True,
            ).distinct()
        )
    return []


@transaction.atomic
def start_approval(target_obj, user):
    target_type = _resolve_target_type(target_obj)
    flow = get_flow_for_region(target_type, target_obj.region)
    if not flow:
        raise ValueError('No active approval flow configured for this target type and region')

    content_type = ContentType.objects.get_for_model(target_obj.__class__)
    instance = models.ApprovalInstance.objects.create(
        content_type=content_type,
        object_id=target_obj.id,
        target_type=target_type,
        region=target_obj.region,
        started_by=user,
        current_step=1,
    )

    steps = list(flow.steps.all())
    if not steps:
        instance.status = models.ApprovalInstance.STATUS_APPROVED
        instance.save(update_fields=['status'])
        return instance

    tasks = []
    for index, step in enumerate(steps, start=1):
        assignees = _resolve_step_assignees(step, target_obj.region)
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
        if instance.tasks.filter(status=models.ApprovalTask.STATUS_PENDING).exists():
            for task in instance.tasks.filter(status=models.ApprovalTask.STATUS_PENDING):
                dingtalk.send_dingtalk_todo(
                    task.assignee,
                    title='审批待办提醒',
                    content=f'请审批 {target_type} #{target_obj.id}',
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
    if not approved:
        instance.status = models.ApprovalInstance.STATUS_REJECTED
        instance.save(update_fields=['status'])
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
            dingtalk.send_dingtalk_todo(
                task_item.assignee,
                title='审批待办提醒',
                content=f'请审批 {instance.target_type} #{instance.object_id}',
            )
        return instance

    instance.status = models.ApprovalInstance.STATUS_APPROVED
    instance.save(update_fields=['status'])
    return instance
