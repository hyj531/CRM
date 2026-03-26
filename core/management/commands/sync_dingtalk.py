from django.core.management.base import BaseCommand

from core.services import dingtalk_sync


class Command(BaseCommand):
    help = 'Sync DingTalk departments and users to Region/User'

    def handle(self, *args, **options):
        summary = dingtalk_sync.sync_departments_and_users()
        if summary['departments_total'] == 0:
            self.stdout.write(self.style.WARNING('No departments found.'))
        self.stdout.write(self.style.SUCCESS('DingTalk sync complete.'))
        self.stdout.write(
            'Departments: total={total}, created={created}, updated={updated}, parent_updated={parent_updated}; '
            'Users: total={u_total}, created={u_created}, updated={u_updated}'.format(
                total=summary['departments_total'],
                created=summary['departments_created'],
                updated=summary['departments_updated'],
                parent_updated=summary['departments_parent_updated'],
                u_total=summary['users_total'],
                u_created=summary['users_created'],
                u_updated=summary['users_updated'],
            )
        )
