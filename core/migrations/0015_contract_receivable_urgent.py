from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0014_activity_internal_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='receivable_urgent',
            field=models.BooleanField(default=False, verbose_name='重点催收'),
        ),
    ]
