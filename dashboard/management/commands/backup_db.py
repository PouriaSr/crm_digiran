import os
import shutil
import gzip
from datetime import datetime, timedelta
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'بکاپ خودکار از دیتابیس SQLite'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-days',
            type=int,
            default=30,
            help='تعداد روزهایی که بکاپ‌ها نگه داشته شوند (پیش‌فرض: 30)',
        )
        parser.add_argument(
            '--no-compress',
            action='store_false',
            dest='compress',
            default=True,
            help='غیرفعال کردن فشرده‌سازی بکاپ (پیش‌فرض: فعال)',
        )

    def handle(self, *args, **options):
        keep_days = options['keep_days']
        compress = options['compress']

        # ═══ مسیرها ═══
        db_path = settings.DATABASES['default']['NAME']
        if not os.path.exists(db_path):
            self.stderr.write(self.style.ERROR(f'❌ دیتابیس یافت نشد: {db_path}'))
            return

        backup_dir = Path(settings.BASE_DIR) / 'backups'
        backup_dir.mkdir(exist_ok=True)

        # ═══ ساخت نام فایل بکاپ ═══
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup_name = f'db-backup-{timestamp}.sqlite3'
        backup_path = backup_dir / backup_name

        try:
            # ═══ کپی از دیتابیس ═══
            shutil.copy2(db_path, backup_path)
            self.stdout.write(self.style.SUCCESS(f'✅ بکاپ گرفته شد: {backup_name}'))

            # ═══ فشرده‌سازی ═══
            if compress:
                compressed_path = backup_path.with_suffix('.sqlite3.gz')
                with open(backup_path, 'rb') as f_in:
                    with gzip.open(compressed_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)

                # حذف فایل اصلی فشرده‌نشده
                os.remove(backup_path)

                # محاسبه حجم
                size_mb = compressed_path.stat().st_size / (1024 * 1024)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'🗜 فشرده شد: {compressed_path.name} ({size_mb:.2f} MB)'
                    )
                )
                backup_path = compressed_path
            else:
                self.stdout.write(
                    self.style.NOTICE(f'📁 بدون فشرده‌سازی: {backup_name}')
                )

            # ═══ پاک کردن بکاپ‌های قدیمی ═══
            self.cleanup_old_backups(backup_dir, keep_days)

            # ═══ نمایش آمار ═══
            self.show_stats(backup_dir)

        except Exception as e:
            self.stderr.write(self.style.ERROR(f'❌ خطا در بکاپ: {str(e)}'))
            raise

    def cleanup_old_backups(self, backup_dir, keep_days):
        """پاک کردن بکاپ‌های قدیمی‌تر از keep_days روز"""
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        deleted_count = 0

        for backup_file in backup_dir.glob('db-backup-*'):
            try:
                # استخراج تاریخ از نام فایل
                # نام فایل: db-backup-20251008-143025.sqlite3.gz
                name_parts = backup_file.stem.replace('.sqlite3', '').split('-')
                if len(name_parts) >= 3:
                    date_str = name_parts[2]  # 20251008
                    file_date = datetime.strptime(date_str, '%Y%m%d')

                    if file_date < cutoff_date:
                        backup_file.unlink()
                        deleted_count += 1
                        self.stdout.write(
                            self.style.WARNING(f'🗑 حذف شد: {backup_file.name}')
                        )
            except (ValueError, IndexError):
                continue

        if deleted_count == 0:
            self.stdout.write(self.style.NOTICE('📭 بکاپ قدیمی برای حذف وجود نداشت'))
        else:
            self.stdout.write(
                self.style.SUCCESS(f'✅ {deleted_count} بکاپ قدیمی حذف شد')
            )

    def show_stats(self, backup_dir):
        """نمایش آمار بکاپ‌ها"""
        backups = list(backup_dir.glob('db-backup-*'))
        if not backups:
            return

        total_size = sum(f.stat().st_size for f in backups) / (1024 * 1024)
        self.stdout.write(
            self.style.NOTICE(
                f'\n📊 آمار: {len(backups)} بکاپ موجود | مجموع: {total_size:.2f} MB'
            )
        )