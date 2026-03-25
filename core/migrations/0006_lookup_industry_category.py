from django.db import migrations


def seed_industry_category(apps, schema_editor):
    LookupCategory = apps.get_model('core', 'LookupCategory')
    LookupCategory.objects.get_or_create(
        code='industry',
        defaults={
            'name': '行业',
            'is_active': True,
            'sort_order': 50,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0005_account_fullname_shortname'),
    ]

    operations = [
        migrations.RunPython(seed_industry_category, migrations.RunPython.noop),
    ]
