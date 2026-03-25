from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0004_rolepermission'),
    ]

    operations = [
        migrations.RenameField(
            model_name='account',
            old_name='name',
            new_name='full_name',
        ),
        migrations.AddField(
            model_name='account',
            name='short_name',
            field=models.CharField(blank=True, default='', max_length=100),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='account',
            name='full_name',
            field=models.CharField(max_length=200, unique=True),
        ),
    ]
