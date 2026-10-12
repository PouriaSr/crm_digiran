from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'همگام‌سازی گروه ads_manager با sales + دسترسی‌های تبلیغات'

    def handle(self, *args, **options):
        ads_group, created = Group.objects.get_or_create(name='ads_manager')
        sales_group = Group.objects.filter(name='sales').first()

        if created:
            self.stdout.write(self.style.WARNING('گروه ads_manager ساخته شد.'))
        else:
            self.stdout.write('گروه ads_manager موجود است — همگام می‌شود...')

        # پاک کردن دسترسی‌های قبلی
        ads_group.permissions.clear()

        # ۱. کپی همه‌ی دسترسی‌های sales
        if sales_group:
            sales_perms = list(sales_group.permissions.all())
            ads_group.permissions.add(*sales_perms)
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ {len(sales_perms)} دسترسی از گروه sales کپی شد.'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING('⚠ گروه sales پیدا نشد — فقط دسترسی‌های تبلیغات اضافه می‌شود.')
            )

        # ۲. دسترسی‌های تبلیغات (add/change/view بدون delete)
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
        self.stdout.write(
            self.style.SUCCESS(
                f'✓ {ad_perms.count() + adlog_perms.count()} دسترسی تبلیغات اضافه شد.'
            )
        )

        total = ads_group.permissions.count()
        self.stdout.write(self.style.SUCCESS(f'\n✅ ads_manager الان {total} دسترسی دارد.'))
        self.stdout.write('نمونه‌ها:')
        for p in list(ads_group.permissions.all())[:10]:
            self.stdout.write(f'  - {p.content_type.app_label}.{p.codename}')
        if total > 10:
            self.stdout.write(f'  ... و {total - 10} مورد دیگر')
