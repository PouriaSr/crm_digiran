#!/usr/bin/env python3
"""
Fix: Migration order was wrong (backfill ran before schema change).

Solution: Delete auto-generated AlterField migrations and combine them
with the backfill migrations (AlterField FIRST, then RunPython).
"""

from pathlib import Path

BASE = Path(__file__).resolve().parent

# ============================================================
# 1. Delete auto-generated AlterField migrations
# ============================================================
files_to_delete = [
    'hr/migrations/0006_alter_employee_hire_date.py',
    'sales/migrations/0005_alter_invoice_issue_date.py',
]
for f in files_to_delete:
    p = BASE / f
    if p.exists():
        p.unlink()
        print(f"🗑  Deleted: {f}")


# ============================================================
# 2. Rewrite backfill migrations (AlterField + RunPython)
# ============================================================

HR_MIGRATION = '''from datetime import datetime, time
from django.db import migrations, models
from django.utils import timezone
import django.utils.timezone


def backfill(apps, schema_editor):
    Employee = apps.get_model('hr', 'Employee')
    for emp in Employee.objects.all():
        if emp.hire_date and emp.created_at:
            dt = emp.hire_date
            ct = emp.created_at

            date_part = dt.date() if isinstance(dt, datetime) else dt
            time_part = ct.time() if isinstance(ct, datetime) else time(0, 0)

            combined = datetime.combine(date_part, time_part)
            if timezone.is_naive(combined):
                combined = timezone.make_aware(combined, timezone.get_current_timezone())

            emp.hire_date = combined
            emp.save(update_fields=['hire_date'])


class Migration(migrations.Migration):
    dependencies = [
        ('hr', '0004_alter_employee_mobile_alter_employee_national_id_and_more'),
    ]
    operations = [
        # 1. First, change schema (DATE → DATETIME)
        migrations.AlterField(
            model_name='employee',
            name='hire_date',
            field=models.DateTimeField(
                default=django.utils.timezone.now,
                verbose_name='تاریخ استخدام',
            ),
        ),
        # 2. Then, backfill old records with creation time
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
'''

SALES_MIGRATION = '''from datetime import datetime, time
from django.db import migrations, models
from django.utils import timezone
import django.utils.timezone


def backfill(apps, schema_editor):
    Invoice = apps.get_model('sales', 'Invoice')
    for inv in Invoice.objects.all():
        if inv.issue_date and inv.created_at:
            dt = inv.issue_date
            ct = inv.created_at

            date_part = dt.date() if isinstance(dt, datetime) else dt
            time_part = ct.time() if isinstance(ct, datetime) else time(0, 0)

            combined = datetime.combine(date_part, time_part)
            if timezone.is_naive(combined):
                combined = timezone.make_aware(combined, timezone.get_current_timezone())

            inv.issue_date = combined
            inv.save(update_fields=['issue_date'])


class Migration(migrations.Migration):
    dependencies = [
        ('sales', '0003_alter_invoice_due_date_alter_invoice_issue_date_and_more'),
    ]
    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='issue_date',
            field=models.DateTimeField(
                db_index=True,
                default=django.utils.timezone.now,
                verbose_name='تاریخ صدور',
            ),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
'''

# Write HR migration
hr_path = BASE / 'hr/migrations/0005_backfill_employee_time.py'
hr_path.write_text(HR_MIGRATION, encoding='utf-8')
print(f"✅ Rewrote: hr/migrations/0005_backfill_employee_time.py")

# Write Sales migration
sales_path = BASE / 'sales/migrations/0004_backfill_invoice_time.py'
sales_path.write_text(SALES_MIGRATION, encoding='utf-8')
print(f"✅ Rewrote: sales/migrations/0004_backfill_invoice_time.py")

print("\n🎉 Done!")
print("Now run:")
print("  python manage.py migrate")
print("  python manage.py makemigrations --check  # should say 'No changes detected'")
