from django.core.management.base import BaseCommand

from core.services import dingtalk_client


class Command(BaseCommand):
    help = 'Refresh DingTalk app access token and cache it'

    def add_arguments(self, parser):
        parser.add_argument(
            '--kind',
            choices=['oapi', 'openapi'],
            default='oapi',
            help='Token type to refresh (default: oapi)',
        )

    def handle(self, *args, **options):
        kind = options['kind']
        _, expires_in = dingtalk_client.refresh_app_access_token(kind=kind)
        self.stdout.write(
            self.style.SUCCESS(
                f'DingTalk access token refreshed (kind={kind}, expires_in={expires_in}s)'
            )
        )
