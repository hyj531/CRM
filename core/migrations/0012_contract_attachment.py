from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0011_contract_vendor_company'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContractAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('file', models.FileField(upload_to='contract_attachments/%Y/%m/', verbose_name='附件文件')),
                ('original_name', models.CharField(blank=True, max_length=255, verbose_name='原始文件名')),
                ('description', models.CharField(blank=True, max_length=200, verbose_name='附件备注')),
                ('contract', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='attachments', to='core.contract', verbose_name='合同')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='contractattachment_items', to='core.user', verbose_name='负责人')),
                ('region', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='contractattachment_items', to='core.region', verbose_name='所属区域')),
            ],
            options={
                'verbose_name': '合同附件',
                'verbose_name_plural': '合同附件',
                'ordering': ['-created_at', '-id'],
            },
        ),
    ]
