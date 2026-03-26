from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Region(models.Model):
    name = models.CharField('区域名称', max_length=200)
    code = models.CharField('区域编码', max_length=50, unique=True)
    dingtalk_dept_id = models.CharField('钉钉部门ID', max_length=50, blank=True)
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.PROTECT, related_name='children', verbose_name='上级区域'
    )
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '区域'
        verbose_name_plural = '区域'

    def __str__(self):
        return self.name

    def get_descendant_ids(self):
        ids = []
        queue = [self]
        while queue:
            node = queue.pop(0)
            children = list(node.children.all())
            ids.extend([child.id for child in children])
            queue.extend(children)
        return ids


class Role(models.Model):
    SCOPE_SELF = 'self'
    SCOPE_REGION = 'region'
    SCOPE_REGION_CHILDREN = 'region_and_children'
    SCOPE_ALL = 'all'

    DATA_SCOPE_CHOICES = [
        (SCOPE_SELF, '仅本人'),
        (SCOPE_REGION, '本区域'),
        (SCOPE_REGION_CHILDREN, '本区域及下级'),
        (SCOPE_ALL, '全部'),
    ]

    name = models.CharField('角色名称', max_length=100, unique=True)
    code = models.CharField('角色编码', max_length=50, unique=True)
    data_scope = models.CharField('数据范围', max_length=32, choices=DATA_SCOPE_CHOICES, default=SCOPE_REGION_CHILDREN)

    class Meta:
        verbose_name = '角色'
        verbose_name_plural = '角色'

    def __str__(self):
        return self.name


class RolePermission(models.Model):
    MODULE_LEAD = 'lead'
    MODULE_OPPORTUNITY = 'opportunity'
    MODULE_ACCOUNT = 'account'
    MODULE_CONTACT = 'contact'
    MODULE_QUOTE = 'quote'
    MODULE_CONTRACT = 'contract'
    MODULE_INVOICE = 'invoice'
    MODULE_PAYMENT = 'payment'
    MODULE_ACTIVITY = 'activity'
    MODULE_TASK = 'task'

    MODULE_CHOICES = [
        (MODULE_LEAD, '线索'),
        (MODULE_OPPORTUNITY, '商机'),
        (MODULE_ACCOUNT, '客户'),
        (MODULE_CONTACT, '联系人'),
        (MODULE_QUOTE, '报价'),
        (MODULE_CONTRACT, '合同'),
        (MODULE_INVOICE, '开票'),
        (MODULE_PAYMENT, '回款'),
        (MODULE_ACTIVITY, '商机跟进'),
        (MODULE_TASK, '任务'),
    ]

    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='permissions', verbose_name='角色')
    module = models.CharField('模块', max_length=32, choices=MODULE_CHOICES)
    can_create = models.BooleanField('可创建', default=True)
    can_update = models.BooleanField('可更新', default=True)
    can_delete = models.BooleanField('可删除', default=False)
    can_approve = models.BooleanField('可审批', default=False)

    class Meta:
        unique_together = [('role', 'module')]
        verbose_name = '角色权限'
        verbose_name_plural = '角色权限'

    def __str__(self):
        return f"{self.role.name}:{self.module}"


class User(AbstractUser):
    region = models.ForeignKey(
        Region, null=True, blank=True, on_delete=models.PROTECT, related_name='users', verbose_name='所属区域'
    )
    role = models.ForeignKey(
        Role, null=True, blank=True, on_delete=models.PROTECT, related_name='users', verbose_name='角色'
    )
    dingtalk_user_id = models.CharField('钉钉用户ID', max_length=80, blank=True)
    dingtalk_union_id = models.CharField('钉钉UnionID', max_length=80, blank=True)
    phone = models.CharField('手机号', max_length=50, blank=True)


class TimestampedModel(models.Model):
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at', '-id']


class OwnedRegionModel(TimestampedModel):
    region = models.ForeignKey(Region, on_delete=models.PROTECT, related_name='%(class)s_items', verbose_name='所属区域')
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name='%(class)s_items', verbose_name='负责人')

    class Meta:
        abstract = True
        ordering = ['-created_at', '-id']


class Lead(OwnedRegionModel):
    name = models.CharField('线索名称', max_length=200)
    source = models.CharField('线索来源', max_length=100, blank=True)
    status = models.CharField('状态', max_length=50, default='new')
    description = models.TextField('线索描述', blank=True)
    estimated_value = models.DecimalField('预估金额', max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = '线索'
        verbose_name_plural = '线索'

    def __str__(self):
        return self.name


class Account(OwnedRegionModel):
    STATUS_ACTIVE = 'active'
    STATUS_ARCHIVED = 'archived'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, '启用'),
        (STATUS_ARCHIVED, '归档'),
    ]

    full_name = models.CharField('客户全称', max_length=200, unique=True)
    short_name = models.CharField('客户简称', max_length=100, blank=True)
    customer_level = models.ForeignKey(
        'LookupOption', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='account_customer_levels', verbose_name='客户级别'
    )
    industry = models.CharField('行业', max_length=100, blank=True)
    enterprise_nature = models.ForeignKey(
        'LookupOption', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='account_enterprise_natures', verbose_name='企业性质'
    )
    scale = models.CharField('企业规模', max_length=100, blank=True)
    credit_code = models.CharField('统一社会信用代码', max_length=50, blank=True)
    address = models.CharField('地址', max_length=200, blank=True)
    phone = models.CharField('电话', max_length=50, blank=True)
    website = models.URLField('官网', blank=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    class Meta:
        verbose_name = '客户'
        verbose_name_plural = '客户'

    def __str__(self):
        return self.full_name


class Contact(OwnedRegionModel):
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='contacts', verbose_name='所属客户')
    name = models.CharField('姓名', max_length=200)
    email = models.EmailField('邮箱', blank=True)
    phone = models.CharField('电话', max_length=50, blank=True)
    title = models.CharField('职位', max_length=100, blank=True)
    is_key_person = models.BooleanField('是否关键人', default=False)
    preference = models.CharField('偏好/标签', max_length=200, blank=True)
    remark = models.TextField('备注', blank=True)

    class Meta:
        verbose_name = '联系人'
        verbose_name_plural = '联系人'

    def __str__(self):
        return self.name


class LookupCategory(models.Model):
    code = models.CharField('类别编码', max_length=50, unique=True)
    name = models.CharField('类别名称', max_length=100)
    is_active = models.BooleanField('是否启用', default=True)
    sort_order = models.PositiveIntegerField('排序', default=0)

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = '字典类别'
        verbose_name_plural = '字典类别'

    def __str__(self):
        return self.name


class LookupOption(models.Model):
    category = models.ForeignKey(LookupCategory, on_delete=models.CASCADE, related_name='options', verbose_name='类别')
    code = models.CharField('选项编码', max_length=50)
    name = models.CharField('选项名称', max_length=100)
    is_active = models.BooleanField('是否启用', default=True)
    sort_order = models.PositiveIntegerField('排序', default=0)

    class Meta:
        ordering = ['sort_order', 'id']
        unique_together = [('category', 'code')]
        verbose_name = '字典选项'
        verbose_name_plural = '字典选项'

    def __str__(self):
        return f"{self.category.code}:{self.name}"


class Opportunity(OwnedRegionModel):
    STAGE_LEAD = 'lead'
    STAGE_OPPORTUNITY = 'opportunity'
    STAGE_DEMAND = 'demand'
    STAGE_SOLUTION = 'solution'
    STAGE_BUSINESS = 'business'
    STAGE_CONTRACT = 'contract'
    STAGE_WON = 'won'
    STAGE_FRAMEWORK = 'framework'
    STAGE_LOST = 'lost'

    STAGES = [
        (STAGE_LEAD, '线索阶段'),
        (STAGE_OPPORTUNITY, '商机阶段'),
        (STAGE_DEMAND, '需求引导'),
        (STAGE_SOLUTION, '方案阶段'),
        (STAGE_BUSINESS, '商务谈判'),
        (STAGE_CONTRACT, '合同审批'),
        (STAGE_WON, '成交关闭'),
        (STAGE_FRAMEWORK, '框架合作'),
        (STAGE_LOST, '商机关闭'),
    ]

    opportunity_name = models.CharField('商机名称', max_length=200)
    account = models.ForeignKey(
        Account, null=True, blank=True, on_delete=models.PROTECT, related_name='opportunities', verbose_name='客户'
    )
    contact = models.ForeignKey(
        Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name='opportunities', verbose_name='联系人'
    )
    lead = models.ForeignKey(
        Lead, null=True, blank=True, on_delete=models.SET_NULL, related_name='opportunities', verbose_name='线索'
    )
    expected_amount = models.DecimalField('预计成交金额', max_digits=12, decimal_places=2, null=True, blank=True)
    expected_close_date = models.DateField('预计成交时间', null=True, blank=True)
    actual_amount = models.DecimalField('实际成交金额', max_digits=12, decimal_places=2, null=True, blank=True)
    actual_close_date = models.DateField('商机成交时间', null=True, blank=True)
    kpi_25_met = models.BooleanField('是否满足经营指标25%', null=True, blank=True)
    opportunity_category = models.ForeignKey(
        LookupOption, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='opportunity_categories', verbose_name='商机分类'
    )
    customer_level = models.ForeignKey(
        LookupOption, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='opportunity_customer_levels', verbose_name='客户级别'
    )
    lead_source = models.ForeignKey(
        LookupOption, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='opportunity_lead_sources', verbose_name='线索来源'
    )
    product_need = models.ForeignKey(
        LookupOption, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='opportunity_product_needs', verbose_name='需求产品'
    )
    user_group = models.ForeignKey(
        LookupOption, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='opportunity_user_groups', verbose_name='用户群体'
    )
    enterprise_nature = models.ForeignKey(
        LookupOption, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='opportunity_enterprise_natures', verbose_name='企业性质'
    )
    has_intermediary = models.BooleanField('是否有居间', null=True, blank=True)
    suspended_at = models.DateField('商机挂起时间', null=True, blank=True)
    latest_followup_note = models.TextField('最新跟进记录', null=True, blank=True)
    latest_followup_at = models.DateTimeField('最新跟进记录时间', null=True, blank=True)
    remark = models.TextField('备注', null=True, blank=True)
    stage = models.CharField('商机阶段', max_length=32, choices=STAGES, default=STAGE_LEAD)
    stage_entered_at = models.DateTimeField('阶段进入时间', null=True, blank=True)
    win_probability = models.PositiveIntegerField('成交概率%', null=True, blank=True)

    class Meta:
        verbose_name = '商机'
        verbose_name_plural = '商机'

    def __str__(self):
        return self.opportunity_name


class OpportunityAttachment(OwnedRegionModel):
    opportunity = models.ForeignKey(
        Opportunity, on_delete=models.PROTECT, related_name='attachments', verbose_name='商机'
    )
    file = models.FileField('附件文件', upload_to='opportunity_attachments/%Y/%m/')
    original_name = models.CharField('原始文件名', max_length=255, blank=True)
    description = models.CharField('附件备注', max_length=200, blank=True)

    class Meta:
        verbose_name = '商机附件'
        verbose_name_plural = '商机附件'

    def __str__(self):
        return self.original_name or self.file.name


class Activity(OwnedRegionModel):
    TYPES = [
        ('call', '电话'),
        ('meeting', '会议'),
        ('email', '邮件'),
        ('visit', '拜访'),
    ]

    activity_type = models.CharField('跟进方式', max_length=20, choices=TYPES, default='call')
    subject = models.CharField('跟进主题', max_length=200)
    description = models.TextField('跟进内容', blank=True)
    lead = models.ForeignKey(
        Lead, null=True, blank=True, on_delete=models.SET_NULL, related_name='activities', verbose_name='线索'
    )
    opportunity = models.ForeignKey(
        Opportunity, null=True, blank=True, on_delete=models.SET_NULL, related_name='activities', verbose_name='商机'
    )
    account = models.ForeignKey(
        Account, null=True, blank=True, on_delete=models.SET_NULL, related_name='activities', verbose_name='客户'
    )
    due_at = models.DateTimeField('跟进时间', null=True, blank=True)

    class Meta:
        verbose_name = '商机跟进'
        verbose_name_plural = '商机跟进'

    def __str__(self):
        return self.subject


class Task(OwnedRegionModel):
    STATUSES = [
        ('open', '进行中'),
        ('done', '已完成'),
        ('canceled', '已取消'),
    ]

    subject = models.CharField('任务标题', max_length=200)
    status = models.CharField('状态', max_length=20, choices=STATUSES, default='open')
    due_at = models.DateTimeField('截止时间', null=True, blank=True)
    lead = models.ForeignKey(
        Lead, null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks', verbose_name='线索'
    )
    opportunity = models.ForeignKey(
        Opportunity, null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks', verbose_name='商机'
    )
    account = models.ForeignKey(
        Account, null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks', verbose_name='客户'
    )
    contract = models.ForeignKey(
        'Contract', null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks', verbose_name='合同'
    )

    class Meta:
        verbose_name = '任务'
        verbose_name_plural = '任务'

    def __str__(self):
        return self.subject


class Quote(OwnedRegionModel):
    STATUSES = [
        ('draft', '草稿'),
        ('submitted', '已提交'),
        ('approved', '已审批'),
        ('rejected', '已驳回'),
    ]

    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='quotes', verbose_name='客户')
    opportunity = models.ForeignKey(
        Opportunity, null=True, blank=True, on_delete=models.SET_NULL, related_name='quotes', verbose_name='商机'
    )
    amount = models.DecimalField('报价金额', max_digits=12, decimal_places=2)
    status = models.CharField('报价状态', max_length=20, choices=STATUSES, default='draft')
    issued_at = models.DateField('报价日期', null=True, blank=True)

    class Meta:
        verbose_name = '报价'
        verbose_name_plural = '报价'

    def __str__(self):
        return f"Quote {self.id}"


class Contract(OwnedRegionModel):
    STATUSES = [
        ('draft', '草稿'),
        ('signed', '已签署'),
        ('active', '执行中'),
        ('closed', '已关闭'),
    ]
    APPROVAL_STATUSES = [
        ('pending', '待审批'),
        ('approved', '已审批'),
        ('rejected', '已驳回'),
    ]

    contract_no = models.CharField('合同编号', max_length=100, blank=True)
    name = models.CharField('合同名称', max_length=200, blank=True)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='contracts', verbose_name='客户')
    vendor_company = models.ForeignKey(
        LookupOption, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='contract_vendor_companies', verbose_name='乙方公司'
    )
    opportunity = models.ForeignKey(
        Opportunity, null=True, blank=True, on_delete=models.SET_NULL, related_name='contracts', verbose_name='商机'
    )
    amount = models.DecimalField('合同金额', max_digits=12, decimal_places=2)
    current_output = models.DecimalField('当前产值', max_digits=12, decimal_places=2, null=True, blank=True)
    final_settlement_amount = models.DecimalField('最终结算金额', max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField('合同状态', max_length=20, choices=STATUSES, default='draft')
    approval_status = models.CharField('审批状态', max_length=20, choices=APPROVAL_STATUSES, default='pending')
    signed_at = models.DateField('签署日期', null=True, blank=True)
    start_date = models.DateField('生效日期', null=True, blank=True)
    end_date = models.DateField('到期日期', null=True, blank=True)

    class Meta:
        verbose_name = '合同'
        verbose_name_plural = '合同'

    def __str__(self):
        return f"Contract {self.id}"


class ContractAttachment(OwnedRegionModel):
    contract = models.ForeignKey(
        Contract, on_delete=models.PROTECT, related_name='attachments', verbose_name='合同'
    )
    file = models.FileField('附件文件', upload_to='contract_attachments/%Y/%m/')
    original_name = models.CharField('原始文件名', max_length=255, blank=True)
    description = models.CharField('附件备注', max_length=200, blank=True)

    class Meta:
        verbose_name = '合同附件'
        verbose_name_plural = '合同附件'

    def __str__(self):
        return self.original_name or self.file.name


class Invoice(OwnedRegionModel):
    STATUSES = [
        ('draft', '草稿'),
        ('issued', '已开票'),
        ('paid', '已回款'),
        ('void', '作废'),
    ]
    APPROVAL_STATUSES = [
        ('pending', '待审批'),
        ('approved', '已审批'),
        ('rejected', '已驳回'),
    ]
    INVOICE_TYPES = [
        ('special', '专票'),
        ('normal', '普票'),
    ]

    invoice_no = models.CharField('开票编号', max_length=100, blank=True)
    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name='invoices', verbose_name='合同')
    account = models.ForeignKey(
        Account, null=True, blank=True, on_delete=models.SET_NULL, related_name='invoices', verbose_name='客户'
    )
    amount = models.DecimalField('开票金额', max_digits=12, decimal_places=2)
    tax_rate = models.DecimalField('税率', max_digits=5, decimal_places=2, null=True, blank=True)
    invoice_type = models.CharField('开票类型', max_length=20, choices=INVOICE_TYPES, default='normal')
    status = models.CharField('开票状态', max_length=20, choices=STATUSES, default='draft')
    approval_status = models.CharField('审批状态', max_length=20, choices=APPROVAL_STATUSES, default='pending')
    issued_at = models.DateField('开票日期', null=True, blank=True)

    class Meta:
        verbose_name = '开票申请'
        verbose_name_plural = '开票申请'

    def __str__(self):
        return f"Invoice {self.id}"


class Payment(OwnedRegionModel):
    STATUSES = [
        ('planned', '计划中'),
        ('partial', '部分回款'),
        ('paid', '已回款'),
    ]

    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name='payments', verbose_name='合同')
    invoice = models.ForeignKey(
        Invoice, null=True, blank=True, on_delete=models.SET_NULL, related_name='payments', verbose_name='开票'
    )
    period_no = models.PositiveIntegerField('回款期次', null=True, blank=True)
    receivable_amount = models.DecimalField('应收金额', max_digits=12, decimal_places=2, null=True, blank=True)
    amount = models.DecimalField('回款金额', max_digits=12, decimal_places=2)
    paid_at = models.DateField('回款日期', null=True, blank=True)
    status = models.CharField('回款状态', max_length=20, choices=STATUSES, default='planned')
    reference = models.CharField('回款编号/备注', max_length=100, blank=True)

    class Meta:
        verbose_name = '回款'
        verbose_name_plural = '回款'

    def __str__(self):
        return f"Payment {self.id}"


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

    def __str__(self):
        return self.name


class ApprovalStep(models.Model):
    flow = models.ForeignKey(ApprovalFlow, on_delete=models.CASCADE, related_name='steps', verbose_name='流程')
    order = models.PositiveIntegerField('步骤顺序')
    name = models.CharField('步骤名称', max_length=200)
    approver_role = models.ForeignKey(Role, null=True, blank=True, on_delete=models.PROTECT, verbose_name='审批角色')
    approver_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, verbose_name='审批人')

    class Meta:
        ordering = ['order']
        verbose_name = '审批步骤'
        verbose_name_plural = '审批步骤'

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
        User, on_delete=models.PROTECT, related_name='started_approvals', verbose_name='发起人'
    )
    current_step = models.PositiveIntegerField('当前步骤', default=1)

    class Meta:
        verbose_name = '审批实例'
        verbose_name_plural = '审批实例'

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
    assignee = models.ForeignKey(User, on_delete=models.PROTECT, related_name='approval_tasks', verbose_name='审批人')
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_BLOCKED)
    decided_at = models.DateTimeField('处理时间', null=True, blank=True)
    comment = models.TextField('审批意见', blank=True)

    class Meta:
        verbose_name = '审批任务'
        verbose_name_plural = '审批任务'

    def __str__(self):
        return f"ApprovalTask {self.id}"
