from django.core.management.base import BaseCommand

from core import models


DEFAULT_LOOKUPS = {
    'product_need': [],
    'user_group': [],
    'opportunity_category': [],
    'customer_level': [],
    'lead_source': [],
    'enterprise_nature': [
        '解决方案服务商',
        '科技公司',
        '硬件厂商',
        '行业头部企业',
    ],
}


class Command(BaseCommand):
    help = 'Seed lookup categories and default options'

    def handle(self, *args, **options):
        created_categories = 0
        created_options = 0

        for code, options in DEFAULT_LOOKUPS.items():
            category, created = models.LookupCategory.objects.get_or_create(
                code=code,
                defaults={'name': code},
            )
            if created:
                created_categories += 1

            existing = set(
                models.LookupOption.objects.filter(category=category).values_list('code', flat=True)
            )
            for name in options:
                if name in existing:
                    continue
                models.LookupOption.objects.create(
                    category=category,
                    code=name,
                    name=name,
                )
                created_options += 1

        self.stdout.write(self.style.SUCCESS(
            f'Seed complete. Categories created: {created_categories}, options created: {created_options}'
        ))
