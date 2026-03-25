from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0006_lookup_industry_category'),
    ]

    operations = [
        migrations.CreateModel(
            name='OpportunityAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('file', models.FileField(upload_to='opportunity_attachments/%Y/%m/', verbose_name='附件文件')),
                ('original_name', models.CharField(blank=True, max_length=255, verbose_name='原始文件名')),
                ('description', models.CharField(blank=True, max_length=200, verbose_name='附件备注')),
                ('opportunity', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='attachments', to='core.opportunity', verbose_name='商机')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='opportunityattachment_items', to='core.user', verbose_name='负责人')),
                ('region', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='opportunityattachment_items', to='core.region', verbose_name='所属区域')),
            ],
            options={
                'verbose_name': '商机附件',
                'verbose_name_plural': '商机附件',
                'ordering': ['-created_at', '-id'],
            },
        ),
    ]
