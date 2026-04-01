from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.conf import settings

from core.models import Region, Role


class TimestampedModel(models.Model):
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at', '-id']


class ApprovalFlow(TimestampedModel):
    TARGET_QUOTE = 'quote'
    TARGET_CONTRACT = 'contract'
    TARGET_INVOICE = 'invoice'

    TARGET_CHOICES = [
        (TARGET_QUOTE, '报价'),
        (TARGET_CONTRACT, '合同'),
        (TARGET_INVOICE, '开票'),
    ]

    name = models.CharField('流程名称', max_length=200)
    target_type = models.CharField('审批对象', max_length=20, choices=TARGET_CHOICES)
    region = models.ForeignKey(
        Region, null=True, blank=True, on_delete=models.PROTECT, related_name='approval_flows', verbose_name='区域'
    )
    is_active = models.BooleanField('是否启用', default=True)

    class Meta:
        verbose_name = '审批流程'
        verbose_name_plural = '审批流程'
        db_table = 'core_approvalflow'

    def __str__(self):
        return self.name


class ApprovalStep(models.Model):
    flow = models.ForeignKey(ApprovalFlow, on_delete=models.CASCADE, related_name='steps', verbose_name='流程')
    order = models.PositiveIntegerField('步骤顺序')
    name = models.CharField('步骤名称', max_length=200)
    approver_role = models.ForeignKey(Role, null=True, blank=True, on_delete=models.PROTECT, verbose_name='审批角色')
    approver_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, verbose_name='审批人'
    )

    class Meta:
        ordering = ['order']
        verbose_name = '审批步骤'
        verbose_name_plural = '审批步骤'
        db_table = 'core_approvalstep'

    def __str__(self):
        return f"{self.flow.name} - {self.name}"


class ApprovalInstance(TimestampedModel):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING, '待审批'),
        (STATUS_APPROVED, '已审批'),
        (STATUS_REJECTED, '已驳回'),
    ]

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name='对象类型')
    object_id = models.PositiveIntegerField('对象ID')
    content_object = GenericForeignKey('content_type', 'object_id')
    target_type = models.CharField('审批对象', max_length=20, choices=ApprovalFlow.TARGET_CHOICES)
    region = models.ForeignKey(
        Region, on_delete=models.PROTECT, related_name='approval_instances', verbose_name='区域'
    )
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='started_approvals', verbose_name='发起人'
    )
    current_step = models.PositiveIntegerField('当前步骤', default=1)

    class Meta:
        verbose_name = '审批实例'
        verbose_name_plural = '审批实例'
        db_table = 'core_approvalinstance'

    def __str__(self):
        return f"Approval {self.id}"


class ApprovalTask(TimestampedModel):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_BLOCKED = 'blocked'

    STATUS_CHOICES = [
        (STATUS_PENDING, '待处理'),
        (STATUS_APPROVED, '已同意'),
        (STATUS_REJECTED, '已拒绝'),
        (STATUS_BLOCKED, '未轮到'),
    ]

    instance = models.ForeignKey(ApprovalInstance, on_delete=models.CASCADE, related_name='tasks', verbose_name='审批实例')
    step = models.ForeignKey(ApprovalStep, on_delete=models.PROTECT, verbose_name='审批步骤')
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='approval_tasks', verbose_name='审批人'
    )
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_BLOCKED)
    decided_at = models.DateTimeField('处理时间', null=True, blank=True)
    comment = models.TextField('审批意见', blank=True)

    class Meta:
        verbose_name = '审批任务'
        verbose_name_plural = '审批任务'
        db_table = 'core_approvaltask'

    def __str__(self):
        return f"ApprovalTask {self.id}"
