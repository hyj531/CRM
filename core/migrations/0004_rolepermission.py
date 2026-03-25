from django.db import migrations, models


def create_default_permissions(apps, schema_editor):
    Role = apps.get_model('core', 'Role')
    RolePermission = apps.get_model('core', 'RolePermission')
    modules = [
        'lead',
        'opportunity',
        'account',
        'contact',
        'quote',
        'contract',
        'invoice',
        'payment',
        'activity',
        'task',
    ]
    for role in Role.objects.all():
        for module in modules:
            RolePermission.objects.get_or_create(
                role=role,
                module=module,
                defaults={
                    'can_create': True,
                    'can_update': True,
                    'can_delete': False,
                    'can_approve': False,
                },
            )


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0003_account_address_account_credit_code_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='RolePermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('module', models.CharField(choices=[('lead', 'Lead'), ('opportunity', 'Opportunity'), ('account', 'Account'), ('contact', 'Contact'), ('quote', 'Quote'), ('contract', 'Contract'), ('invoice', 'Invoice'), ('payment', 'Payment'), ('activity', 'Activity'), ('task', 'Task')], max_length=32)),
                ('can_create', models.BooleanField(default=True)),
                ('can_update', models.BooleanField(default=True)),
                ('can_delete', models.BooleanField(default=False)),
                ('can_approve', models.BooleanField(default=False)),
                ('role', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='permissions', to='core.role')),
            ],
            options={
                'unique_together': {('role', 'module')},
            },
        ),
        migrations.RunPython(create_default_permissions, migrations.RunPython.noop),
    ]
