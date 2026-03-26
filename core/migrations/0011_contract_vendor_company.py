from django.db import migrations, models
import django.db.models.deletion


def seed_vendor_company_category(apps, schema_editor):
    LookupCategory = apps.get_model('core', 'LookupCategory')
    LookupCategory.objects.get_or_create(
        code='vendor_company',
        defaults={
            'name': '乙方公司',
            'is_active': True,
            'sort_order': 60,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0010_alter_account_options_alter_activity_options_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_vendor_company_category, migrations.RunPython.noop),
        migrations.AddField(
            model_name='contract',
            name='vendor_company',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='contract_vendor_companies',
                to='core.lookupoption',
                verbose_name='乙方公司',
            ),
        ),
    ]
