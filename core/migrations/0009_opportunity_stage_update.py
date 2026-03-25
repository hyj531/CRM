from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0008_opportunity_remark'),
    ]

    operations = [
        migrations.AlterField(
            model_name='opportunity',
            name='stage',
            field=models.CharField(
                choices=[
                    ('lead', '线索阶段'),
                    ('opportunity', '商机阶段'),
                    ('demand', '需求引导'),
                    ('solution', '方案阶段'),
                    ('business', '商务谈判'),
                    ('contract', '合同审批'),
                    ('won', '成交关闭'),
                    ('framework', '框架合作'),
                    ('lost', '商机关闭'),
                ],
                default='lead',
                max_length=32,
                verbose_name='商机阶段',
            ),
        ),
    ]
