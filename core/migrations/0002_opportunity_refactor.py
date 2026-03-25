# Generated manually for opportunity refactor

from django.db import migrations, models
import django.db.models.deletion


def migrate_opportunity_stage(apps, schema_editor):
    Opportunity = apps.get_model('core', 'Opportunity')
    stage_map = {
        'new': 'demand',
        'qualified': 'solution',
        'proposal': 'solution',
        'negotiation': 'business',
        'won': 'won',
        'lost': 'lost',
        'demand': 'demand',
        'solution': 'solution',
        'business': 'business',
        'contract': 'contract',
    }
    prob_map = {
        'demand': 10,
        'solution': 30,
        'business': 70,
        'contract': 90,
        'won': 100,
        'lost': 0,
    }

    for opp in Opportunity.objects.all():
        new_stage = stage_map.get(opp.stage, 'demand')
        updates = {}
        if opp.stage != new_stage:
            updates['stage'] = new_stage
        if not opp.stage_entered_at:
            updates['stage_entered_at'] = opp.updated_at or opp.created_at
        if opp.win_probability is None:
            updates['win_probability'] = prob_map.get(new_stage, 0)
        if updates:
            for key, value in updates.items():
                setattr(opp, key, value)
            opp.save(update_fields=list(updates.keys()))


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LookupCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=50, unique=True)),
                ('name', models.CharField(max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
            ],
            options={
                'ordering': ['sort_order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='LookupOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=50)),
                ('name', models.CharField(max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='options', to='core.lookupcategory')),
            ],
            options={
                'ordering': ['sort_order', 'id'],
                'unique_together': {('category', 'code')},
            },
        ),
        migrations.RenameField(
            model_name='opportunity',
            old_name='name',
            new_name='opportunity_name',
        ),
        migrations.RenameField(
            model_name='opportunity',
            old_name='value',
            new_name='expected_amount',
        ),
        migrations.AddField(
            model_name='opportunity',
            name='actual_amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='actual_close_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='contact',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='opportunities', to='core.contact'),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='customer_level',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='opportunity_customer_levels', to='core.lookupoption'),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='enterprise_nature',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='opportunity_enterprise_natures', to='core.lookupoption'),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='has_intermediary',
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='kpi_25_met',
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='latest_followup_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='latest_followup_note',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='lead_source',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='opportunity_lead_sources', to='core.lookupoption'),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='opportunity_category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='opportunity_categories', to='core.lookupoption'),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='product_need',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='opportunity_product_needs', to='core.lookupoption'),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='stage_entered_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='suspended_at',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='user_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='opportunity_user_groups', to='core.lookupoption'),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='win_probability',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='opportunity',
            name='stage',
            field=models.CharField(choices=[('demand', '需求引导'), ('solution', '方案阶段'), ('business', '商务谈判'), ('contract', '合同审批'), ('won', '成交关闭'), ('lost', '丢单')], default='demand', max_length=32),
        ),
        migrations.AddField(
            model_name='contract',
            name='final_settlement_amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.RunPython(migrate_opportunity_stage, migrations.RunPython.noop),
    ]
