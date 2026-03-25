from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0007_opportunity_attachment'),
    ]

    operations = [
        migrations.AddField(
            model_name='opportunity',
            name='remark',
            field=models.TextField(blank=True, null=True, verbose_name='备注'),
        ),
    ]
