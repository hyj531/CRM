from django.core.management.base import BaseCommand

from approval.services import todo


class Command(BaseCommand):
    help = 'Process approval DingTalk todo outbox queue'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=100, help='Number of outbox records per round')
        parser.add_argument('--max-rounds', type=int, default=1, help='Max processing rounds in one execution')

    def handle(self, *args, **options):
        batch_size = max(int(options.get('batch_size') or 100), 1)
        max_rounds = max(int(options.get('max_rounds') or 1), 1)

        total = {'processed': 0, 'succeeded': 0, 'failed': 0, 'dead': 0}
        for _ in range(max_rounds):
            summary = todo.process_outbox(batch_size=batch_size)
            for key in total:
                total[key] += int(summary.get(key, 0))
            if summary.get('processed', 0) == 0:
                break

        self.stdout.write(
            self.style.SUCCESS(
                f"approval todo outbox processed={total['processed']} "
                f"succeeded={total['succeeded']} failed={total['failed']} dead={total['dead']}"
            )
        )
