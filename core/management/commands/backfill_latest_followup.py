from django.core.management.base import BaseCommand

from core import models
from core.services import followup


class Command(BaseCommand):
    help = 'Backfill opportunity latest followup fields from activities.'

    def add_arguments(self, parser):
        parser.add_argument('--ids', type=str, help='Comma-separated opportunity ids')
        parser.add_argument('--dry-run', action='store_true', help='Only count, no updates')

    def handle(self, *args, **options):
        ids = options.get('ids')
        dry_run = options.get('dry_run')
        queryset = models.Opportunity.objects.all()
        if ids:
            id_list = [int(item) for item in ids.split(',') if item.strip().isdigit()]
            queryset = queryset.filter(id__in=id_list)
        total = queryset.count()
        self.stdout.write(f'Backfilling {total} opportunity records...')
        if dry_run:
            return
        updated = 0
        for opp in queryset.iterator():
            activity = followup.update_opportunity_latest_followup(opp.id)
            if activity:
                updated += 1
        self.stdout.write(f'Backfill complete. Updated: {updated}')
