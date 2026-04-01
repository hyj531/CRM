from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0015_contract_receivable_urgent'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='ApprovalTask'),
                migrations.DeleteModel(name='ApprovalInstance'),
                migrations.DeleteModel(name='ApprovalStep'),
                migrations.DeleteModel(name='ApprovalFlow'),
            ],
            database_operations=[],
        ),
    ]
