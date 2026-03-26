from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0013_contract_current_output'),
    ]

    operations = [
        migrations.AlterField(
            model_name='activity',
            name='activity_type',
            field=models.CharField(
                choices=[
                    ('call', '电话'),
                    ('meeting', '会议'),
                    ('email', '邮件'),
                    ('visit', '拜访'),
                    ('internal', '内部穿透'),
                ],
                default='internal',
                max_length=20,
                verbose_name='跟进方式',
            ),
        ),
    ]
