from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('core', '0015_contract_receivable_urgent'),
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='ApprovalFlow',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                        ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                        ('name', models.CharField(max_length=200, verbose_name='流程名称')),
                        ('target_type', models.CharField(choices=[('quote', '报价'), ('contract', '合同'), ('invoice', '开票')], max_length=20, verbose_name='审批对象')),
                        ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                        ('region', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='approval_flows', to='core.region', verbose_name='区域')),
                    ],
                    options={
                        'verbose_name': '审批流程',
                        'verbose_name_plural': '审批流程',
                        'db_table': 'core_approvalflow',
                    },
                ),
                migrations.CreateModel(
                    name='ApprovalInstance',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                        ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                        ('object_id', models.PositiveIntegerField(verbose_name='对象ID')),
                        ('target_type', models.CharField(choices=[('quote', '报价'), ('contract', '合同'), ('invoice', '开票')], max_length=20, verbose_name='审批对象')),
                        ('status', models.CharField(choices=[('pending', '待审批'), ('approved', '已审批'), ('rejected', '已驳回')], default='pending', max_length=20, verbose_name='状态')),
                        ('current_step', models.PositiveIntegerField(default=1, verbose_name='当前步骤')),
                        ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype', verbose_name='对象类型')),
                        ('region', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='approval_instances', to='core.region', verbose_name='区域')),
                        ('started_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='started_approvals', to=settings.AUTH_USER_MODEL, verbose_name='发起人')),
                    ],
                    options={
                        'verbose_name': '审批实例',
                        'verbose_name_plural': '审批实例',
                        'db_table': 'core_approvalinstance',
                    },
                ),
                migrations.CreateModel(
                    name='ApprovalStep',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('order', models.PositiveIntegerField(verbose_name='步骤顺序')),
                        ('name', models.CharField(max_length=200, verbose_name='步骤名称')),
                        ('approver_role', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='core.role', verbose_name='审批角色')),
                        ('approver_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, verbose_name='审批人')),
                        ('flow', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='steps', to='approval.approvalflow', verbose_name='流程')),
                    ],
                    options={
                        'verbose_name': '审批步骤',
                        'verbose_name_plural': '审批步骤',
                        'ordering': ['order'],
                        'db_table': 'core_approvalstep',
                    },
                ),
                migrations.CreateModel(
                    name='ApprovalTask',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                        ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                        ('status', models.CharField(choices=[('pending', '待处理'), ('approved', '已同意'), ('rejected', '已拒绝'), ('blocked', '未轮到')], default='blocked', max_length=20, verbose_name='状态')),
                        ('decided_at', models.DateTimeField(blank=True, null=True, verbose_name='处理时间')),
                        ('comment', models.TextField(blank=True, verbose_name='审批意见')),
                        ('assignee', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='approval_tasks', to=settings.AUTH_USER_MODEL, verbose_name='审批人')),
                        ('instance', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tasks', to='approval.approvalinstance', verbose_name='审批实例')),
                        ('step', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='approval.approvalstep', verbose_name='审批步骤')),
                    ],
                    options={
                        'verbose_name': '审批任务',
                        'verbose_name_plural': '审批任务',
                        'db_table': 'core_approvaltask',
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
