"""
همگام‌سازی گروه «مسئول تبلیغات» با دسترسی‌های Django.

⚠️ توجه: نام گروه‌ها باید از ROLE_TO_GROUP بیاد (فارسی)، نه hardcode انگلیسی.
"""
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from accounts.permissions import (
    ROLE_TO_GROUP,
    ROLE_SALES,
    ROLE_ADS_MANAGER,
)


class Command(BaseCommand):
    help = 'همگام‌سازی گروه «مسئول تبلیغات» با دسترسی‌های sales + تبلیغات'

    def handle(self, *args, **options):
        # ═══ ۱. نام‌های گروه از منبع واحد (permissions.py) ═══
        ads_group_name = ROLE_TO_GROUP[ROLE_ADS_MANAGER]   # 'مسئول تبلیغات'
        sales_group_name = ROLE_TO_GROUP[ROLE_SALES]        # 'کارشناس فروش'

        ads_group, created = Group.objects.get_or_create(name=ads_group_name)
        sales_group = Group.objects.filter(name=sales_group_name).first()

        if created:
            self.stdout.write(self.style.WARNING(
                f'گروه «{ads_group_name}» ساخته شد.'
            ))
        else:
            self.stdout.write(f'گروه «{ads_group_name}» موجود است — همگام می‌شود...')

        # ═══ ۲. پاک‌سازی دسترسی‌های قبلی ═══
        ads_group.permissions.clear()

        # ═══ ۳. کپی دسترسی‌های sales ═══
        if sales_group:
            sales_perms = list(sales_group.permissions.all())
            if sales_perms:
                ads_group.permissions.add(*sales_perms)
                self.stdout.write(self.style.SUCCESS(
                    f'✓ {len(sales_perms)} دسترسی از «{sales_group_name}» کپی شد.'
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f'⚠ گروه «{sales_group_name}» هیچ Django permission ندارد — '
                    'Django perms کپی نشد.'
                ))
        else:
            self.stdout.write(self.style.WARNING(
                f'⚠ گروه «{sales_group_name}» پیدا نشد.'
            ))

        # ═══ ۴. دسترسی‌های تبلیغات ═══
        ad_ct = ContentType.objects.get(app_label='ads', model='ad')
        adlog_ct = ContentType.objects.get(app_label='ads', model='adlog')

        ad_perms = Permission.objects.filter(
            content_type=ad_ct,
            codename__in=['add_ad', 'change_ad', 'view_ad'],
        )
        adlog_perms = Permission.objects.filter(
            content_type=adlog_ct,
            codename__in=['view_adlog'],
        )

        ads_group.permissions.add(*ad_perms, *adlog_perms)
        self.stdout.write(self.style.SUCCESS(
            f'✓ {ad_perms.count() + adlog_perms.count()} دسترسی تبلیغات اضافه شد.'
        ))

        # ═══ ۵. خلاصه ═══
        total = ads_group.permissions.count()
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ گروه «{ads_group_name}» الان {total} دسترسی Django دارد.'
        ))

        if total > 0:
            self.stdout.write('نمونه‌ها:')
            for p in list(ads_group.permissions.all())[:10]:
                self.stdout.write(f'  - {p.content_type.app_label}.{p.codename}')
            if total > 10:
                self.stdout.write(f'  ... و {total - 10} مورد دیگر')