from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.conf import settings
from django.utils import timezone

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
    STATUS_WITHDRAWN = 'withdrawn'

    STATUS_CHOICES = [
        (STATUS_PENDING, '待审批'),
        (STATUS_APPROVED, '已审批'),
        (STATUS_REJECTED, '已驳回'),
        (STATUS_WITHDRAWN, '已撤回'),
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
    STATUS_CANCELED = 'canceled'

    STATUS_CHOICES = [
        (STATUS_PENDING, '待处理'),
        (STATUS_APPROVED, '已同意'),
        (STATUS_REJECTED, '已拒绝'),
        (STATUS_BLOCKED, '未轮到'),
        (STATUS_CANCELED, '已关闭'),
    ]

    TODO_CHANNEL_OWN_OA = 'own_oa'
    TODO_CHANNEL_TODO_API = 'todo_api'
    TODO_CHANNEL_DISABLED = 'disabled'
    TODO_CHANNEL_UNKNOWN = 'unknown'

    TODO_CHANNEL_CHOICES = [
        (TODO_CHANNEL_OWN_OA, '钉钉自建审批'),
        (TODO_CHANNEL_TODO_API, '钉钉Todo开放接口'),
        (TODO_CHANNEL_DISABLED, '未启用'),
        (TODO_CHANNEL_UNKNOWN, '未知通道'),
    ]

    TODO_STATUS_INIT = 'init'
    TODO_STATUS_QUEUED = 'queued'
    TODO_STATUS_CREATED = 'created'
    TODO_STATUS_COMPLETED = 'completed'
    TODO_STATUS_FAILED = 'failed'
    TODO_STATUS_SKIPPED = 'skipped'

    TODO_STATUS_CHOICES = [
        (TODO_STATUS_INIT, '未处理'),
        (TODO_STATUS_QUEUED, '排队中'),
        (TODO_STATUS_CREATED, '已创建'),
        (TODO_STATUS_COMPLETED, '已完成'),
        (TODO_STATUS_FAILED, '失败'),
        (TODO_STATUS_SKIPPED, '已跳过'),
    ]

    instance = models.ForeignKey(ApprovalInstance, on_delete=models.CASCADE, related_name='tasks', verbose_name='审批实例')
    step = models.ForeignKey(ApprovalStep, on_delete=models.PROTECT, verbose_name='审批步骤')
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='approval_tasks', verbose_name='审批人'
    )
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_BLOCKED)
    decided_at = models.DateTimeField('处理时间', null=True, blank=True)
    comment = models.TextField('审批意见', blank=True)
    todo_source_id = models.CharField('待办来源ID', max_length=120, blank=True)
    todo_task_id = models.CharField('钉钉待办ID', max_length=120, blank=True)
    todo_channel = models.CharField(
        '待办通道', max_length=20, choices=TODO_CHANNEL_CHOICES, default=TODO_CHANNEL_UNKNOWN
    )
    todo_status = models.CharField('待办状态', max_length=20, choices=TODO_STATUS_CHOICES, default=TODO_STATUS_INIT)
    todo_last_error = models.TextField('待办错误信息', blank=True)
    todo_retry_count = models.PositiveIntegerField('待办重试次数', default=0)
    todo_next_retry_at = models.DateTimeField('待办下次重试时间', null=True, blank=True)

    class Meta:
        verbose_name = '审批任务'
        verbose_name_plural = '审批任务'
        db_table = 'core_approvaltask'

    def __str__(self):
        return f"ApprovalTask {self.id}"


class ApprovalActionLog(models.Model):
    ACTION_SUBMITTED = 'submitted'
    ACTION_TASK_ACTIVATED = 'task_activated'
    ACTION_APPROVED = 'approved'
    ACTION_REJECTED = 'rejected'
    ACTION_WITHDRAWN = 'withdrawn'
    ACTION_COMPLETED = 'completed'
    ACTION_TODO_CREATE = 'todo_create'
    ACTION_TODO_COMPLETE = 'todo_complete'
    ACTION_TODO_FAILED = 'todo_failed'

    ACTION_CHOICES = [
        (ACTION_SUBMITTED, '发起审批'),
        (ACTION_TASK_ACTIVATED, '任务激活'),
        (ACTION_APPROVED, '审批通过'),
        (ACTION_REJECTED, '审批驳回'),
        (ACTION_WITHDRAWN, '审批撤回'),
        (ACTION_COMPLETED, '流程完成'),
        (ACTION_TODO_CREATE, '创建待办'),
        (ACTION_TODO_COMPLETE, '完成待办'),
        (ACTION_TODO_FAILED, '待办失败'),
    ]

    instance = models.ForeignKey(
        ApprovalInstance, on_delete=models.CASCADE, related_name='action_logs', verbose_name='审批实例'
    )
    task = models.ForeignKey(
        ApprovalTask, null=True, blank=True, on_delete=models.SET_NULL, related_name='action_logs', verbose_name='审批任务'
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='approval_action_logs', verbose_name='操作人'
    )
    action = models.CharField('动作', max_length=32, choices=ACTION_CHOICES)
    from_status = models.CharField('原状态', max_length=20, blank=True)
    to_status = models.CharField('新状态', max_length=20, blank=True)
    comment = models.TextField('备注', blank=True)
    extra = models.JSONField('扩展数据', default=dict, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '审批动作日志'
        verbose_name_plural = '审批动作日志'
        db_table = 'core_approvalactionlog'
        ordering = ['created_at', 'id']

    def __str__(self):
        return f"ApprovalActionLog {self.id}"


class ApprovalTodoOutbox(models.Model):
    ACTION_CREATE = 'create'
    ACTION_COMPLETE = 'complete'
    ACTION_CHOICES = [
        (ACTION_CREATE, '创建待办'),
        (ACTION_COMPLETE, '完成待办'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    STATUS_DEAD = 'dead'
    STATUS_CHOICES = [
        (STATUS_PENDING, '待处理'),
        (STATUS_PROCESSING, '处理中'),
        (STATUS_SUCCEEDED, '成功'),
        (STATUS_FAILED, '失败待重试'),
        (STATUS_DEAD, '死信'),
    ]

    task = models.ForeignKey(
        ApprovalTask, on_delete=models.CASCADE, related_name='todo_outbox_items', verbose_name='审批任务'
    )
    action = models.CharField('动作', max_length=20, choices=ACTION_CHOICES)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    source_id = models.CharField('来源ID', max_length=120, blank=True)
    payload = models.JSONField('负载数据', default=dict, blank=True)
    retry_count = models.PositiveIntegerField('重试次数', default=0)
    next_retry_at = models.DateTimeField('下次重试时间', default=timezone.now)
    last_error = models.TextField('最后错误', blank=True)
    processed_at = models.DateTimeField('处理时间', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '审批待办队列'
        verbose_name_plural = '审批待办队列'
        db_table = 'core_approvaltodooutbox'
        indexes = [
            models.Index(fields=['status', 'next_retry_at']),
            models.Index(fields=['action', 'source_id']),
        ]

    def __str__(self):
        return f"ApprovalTodoOutbox {self.id}"
