"""
دستور مدیریتی برای حذف لاگ‌های قدیمی — فاز بهبود Audit

استفاده:
    python manage.py cleanup_audit                  # ۹۰ روز اخیر
    python manage.py cleanup_audit --days=30        # ۳۰ روز
    python manage.py cleanup_audit --dry-run        # فقط نمایش
    python manage.py cleanup_audit --keep-created   # نگه‌داری created
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from audit.models import AuditLog


class Command(BaseCommand):
    help = 'حذف لاگ‌های قدیمی‌تر از N روز (پیش‌فرض: ۹۰)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='حذف لاگ‌های قدیمی‌تر از N روز (پیش‌فرض: 90)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='فقط نمایش تعداد — بدون حذف',
        )
        parser.add_argument(
            '--keep-created',
            action='store_true',
            help='نگه‌داری لاگ‌های created (فقط updated/deleted حذف بشن)',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        keep_created = options['keep_created']

        cutoff = timezone.now() - timedelta(days=days)
        qs = AuditLog.objects.filter(created_at__lt=cutoff)

        if keep_created:
            qs = qs.exclude(action=AuditLog.ACTION_CREATED)

        count = qs.count()
        oldest = qs.order_by('created_at').first()

        if count == 0:
            self.stdout.write(self.style.WARNING(
                f'هیچ لاگی قدیمی‌تر از {days} روز یافت نشد.'
            ))
            return

        # ─── خلاصه ───
        self.stdout.write(f'\n📊 خلاصه:')
        self.stdout.write(f'   تاریخ مرجع: قبل از {cutoff.strftime("%Y-%m-%d %H:%M")}')
        self.stdout.write(f'   تعداد رکورد: {count}')
        if oldest:
            self.stdout.write(f'   قدیمی‌ترین: {oldest.created_at.strftime("%Y-%m-%d %H:%M")}')
        if keep_created:
            self.stdout.write(f'   حالت: نگه‌داری created — فقط updated/deleted حذف می‌شن')

        # ─── حذف ───
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'\n🔍 حالت dry-run — هیچ تغییری اعمال نشد.'
            ))
            return

        confirm = input(f'\n⚠️  {count} رکورد حذف خواهد شد. ادامه می‌دهید؟ [y/N]: ')
        if confirm.lower() != 'y':
            self.stdout.write(self.style.NOTICE('لغو شد.'))
            return

        deleted, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ {deleted} رکورد حذف شد.'
        ))
