from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0012_contract_attachment'),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='current_output',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='当前产值'),
        ),
    ]
