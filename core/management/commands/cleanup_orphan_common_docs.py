import posixpath

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError

from core import models


class Command(BaseCommand):
    help = 'Delete orphan files under common_documents that are no longer referenced by CommonDocument records.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--prefix',
            type=str,
            default='common_documents',
            help='Storage path prefix to scan (default: common_documents)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only print orphan file count, do not delete files.',
        )

    def _iter_storage_files(self, storage, prefix):
        dirs, files = storage.listdir(prefix)
        for name in files:
            yield posixpath.join(prefix, name)
        for dirname in dirs:
            child_prefix = posixpath.join(prefix, dirname)
            yield from self._iter_storage_files(storage, child_prefix)

    def handle(self, *args, **options):
        prefix = (options.get('prefix') or 'common_documents').strip().strip('/')
        dry_run = bool(options.get('dry_run'))
        storage = default_storage

        db_files = set(
            models.CommonDocument.objects.exclude(file='').values_list('file', flat=True)
        )

        if not prefix:
            raise CommandError('prefix 不能为空。')

        if not storage.exists(prefix):
            self.stdout.write(self.style.WARNING(f'路径不存在，无需清理: {prefix}'))
            return

        try:
            storage_files = set(self._iter_storage_files(storage, prefix))
        except (NotImplementedError, AttributeError):
            raise CommandError('当前存储后端不支持遍历目录（listdir）。')

        orphan_files = sorted(storage_files - db_files)
        self.stdout.write(f'扫描路径: {prefix}')
        self.stdout.write(f'数据库文件数: {len(db_files)}')
        self.stdout.write(f'存储文件数: {len(storage_files)}')
        self.stdout.write(f'孤儿文件数: {len(orphan_files)}')

        if dry_run:
            for name in orphan_files[:50]:
                self.stdout.write(f'  - {name}')
            if len(orphan_files) > 50:
                self.stdout.write(f'  ... 其余 {len(orphan_files) - 50} 个文件省略')
            self.stdout.write(self.style.WARNING('dry-run 模式，未执行删除。'))
            return

        deleted = 0
        failed = 0
        for name in orphan_files:
            try:
                storage.delete(name)
                deleted += 1
            except Exception as exc:
                failed += 1
                self.stderr.write(f'删除失败: {name} ({exc})')

        self.stdout.write(self.style.SUCCESS(f'清理完成，已删除: {deleted}'))
        if failed:
            self.stdout.write(self.style.WARNING(f'删除失败: {failed}'))
