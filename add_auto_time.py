#!/usr/bin/env python3
"""
1. Convert DateFields to DateTimeFields for auto-recorded entries.
2. Update views to filter by date properly.
3. Update templates to show both Date and Time (Persian).
4. Generate data migrations to backfill old records with creation time.
"""

import re
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent

# ============================================================
# 1. Update Models
# ============================================================
def patch_models():
    print("🔧 Patching models...")

    # sales/models.py
    p = BASE / 'sales' / 'models.py'
    if p.exists():
        c = p.read_text(encoding='utf-8')
        c = c.replace(
            "issue_date = models.DateField('تاریخ صدور', default=timezone.now, db_index=True)",
            "issue_date = models.DateTimeField('تاریخ صدور', default=timezone.now, db_index=True)"
        )
        p.write_text(c, encoding='utf-8')
        print("  ✅ sales/models.py updated")

    # hr/models.py
    p = BASE / 'hr' / 'models.py'
    if p.exists():
        c = p.read_text(encoding='utf-8')
        c = c.replace(
            "hire_date = models.DateField('تاریخ استخدام', default=timezone.now)",
            "hire_date = models.DateTimeField('تاریخ استخدام', default=timezone.now)"
        )
        p.write_text(c, encoding='utf-8')
        print("  ✅ hr/models.py updated")

# ============================================================
# 2. Update Views (Filtering)
# ============================================================
def patch_views():
    print("\n🔧 Patching views for safe filtering...")
    p = BASE / 'sales' / 'views.py'
    if p.exists():
        c = p.read_text(encoding='utf-8')
        c = c.replace("qs = qs.filter(issue_date__gte=from_date)", "qs = qs.filter(issue_date__date__gte=from_date)")
        c = c.replace("qs = qs.filter(issue_date__lte=to_date)", "qs = qs.filter(issue_date__date__lte=to_date)")
        p.write_text(c, encoding='utf-8')
        print("  ✅ sales/views.py updated")

# ============================================================
# 3. Update Templates (Show Date + Time)
# ============================================================
def patch_templates():
    print("\n🔧 Patching templates (Date + Time)...")
    
    # sales/list.html
    p = BASE / 'templates' / 'sales' / 'list.html'
    if p.exists():
        c = p.read_text(encoding='utf-8')
        c = c.replace('{{ invoice.issue_date|jdate:"Y/m/d" }}', '{{ invoice.issue_date|jdate:"Y/m/d H:i" }}')
        p.write_text(c, encoding='utf-8')
        print("  ✅ sales/list.html updated")

    # sales/detail.html
    p = BASE / 'templates' / 'sales' / 'detail.html'
    if p.exists():
        c = p.read_text(encoding='utf-8')
        c = c.replace('{{ invoice.issue_date|jdate:"Y/m/d" }}', '{{ invoice.issue_date|jdate:"Y/m/d H:i" }}')
        p.write_text(c, encoding='utf-8')
        print("  ✅ sales/detail.html updated")

    # sales/print.html
    p = BASE / 'templates' / 'sales' / 'print.html'
    if p.exists():
        c = p.read_text(encoding='utf-8')
        c = c.replace('{{ invoice.issue_date|jdate:"Y/m/d"|fa_digits }}', '{{ invoice.issue_date|jdate:"Y/m/d H:i"|fa_digits }}')
        p.write_text(c, encoding='utf-8')
        print("  ✅ sales/print.html updated")

    # hr/employee_list.html
    p = BASE / 'templates' / 'hr' / 'employee_list.html'
    if p.exists():
        c = p.read_text(encoding='utf-8')
        c = c.replace('{{ emp.hire_date|jdate:"Y/m/d" }}', '{{ emp.hire_date|jdate:"Y/m/d H:i" }}')
        p.write_text(c, encoding='utf-8')
        print("  ✅ hr/employee_list.html updated")

    # hr/employee_detail.html
    p = BASE / 'templates' / 'hr' / 'employee_detail.html'
    if p.exists():
        c = p.read_text(encoding='utf-8')
        c = c.replace('{{ employee.hire_date|jdate:"Y/m/d" }}', '{{ employee.hire_date|jdate:"Y/m/d H:i" }}')
        p.write_text(c, encoding='utf-8')
        print("  ✅ hr/employee_detail.html updated")

    # hr/attendance_list.html
    p = BASE / 'templates' / 'hr' / 'attendance_list.html'
    if p.exists():
        c = p.read_text(encoding='utf-8')
        c = c.replace('<th class="text-right px-4 py-3 font-medium">تاریخ</th>', '<th class="text-right px-4 py-3 font-medium">تاریخ و زمان ثبت</th>')
        c = c.replace('{{ att.date|jdate:"Y/m/d" }}', '{{ att.date|jdate:"Y/m/d" }} <span class="text-gray-400 mx-1">|</span> {{ att.created_at|jdate:"H:i" }}')
        p.write_text(c, encoding='utf-8')
        print("  ✅ hr/attendance_list.html updated")

# ============================================================
# 4. Generate Data Migration for Backfill
# ============================================================
def create_migrations():
    print("\n🔧 Creating data backfill migrations...")

    # Sales Migration
    sales_mig = BASE / 'sales' / 'migrations' / '0004_backfill_invoice_time.py'
    sales_mig.write_text('''from django.db import migrations
from datetime import datetime, time

def backfill_time(apps, schema_editor):
    Invoice = apps.get_model('sales', 'Invoice')
    for inv in Invoice.objects.all():
        if inv.issue_date and inv.created_at:
            # Combine old date with creation time
            inv.issue_date = datetime.combine(inv.issue_date.date(), inv.created_at.time())
            inv.save(update_fields=['issue_date'])

class Migration(migrations.Migration):
    dependencies = [
        ('sales', '0003_alter_invoice_due_date_alter_invoice_issue_date_and_more'),
    ]
    operations = [
        migrations.RunPython(backfill_time, migrations.RunPython.noop),
    ]
''', encoding='utf-8')
    print("  ✅ sales/migrations/0004_backfill_invoice_time.py created")

    # HR Migration
    hr_mig = BASE / 'hr' / 'migrations' / '0005_backfill_employee_time.py'
    hr_mig.write_text('''from django.db import migrations
from datetime import datetime, time

def backfill_time(apps, schema_editor):
    Employee = apps.get_model('hr', 'Employee')
    for emp in Employee.objects.all():
        if emp.hire_date and emp.created_at:
            # Combine old date with creation time
            emp.hire_date = datetime.combine(emp.hire_date.date(), emp.created_at.time())
            emp.save(update_fields=['hire_date'])

class Migration(migrations.Migration):
    dependencies = [
        ('hr', '0004_alter_employee_mobile_alter_employee_national_id_and_more'),
    ]
    operations = [
        migrations.RunPython(backfill_time, migrations.RunPython.noop),
    ]
''', encoding='utf-8')
    print("  ✅ hr/migrations/0005_backfill_employee_time.py created")

if __name__ == '__main__':
    print("🚀 Applying Date & Time enhancements...\n")
    patch_models()
    patch_views()
    patch_templates()
    create_migrations()
    print("\n🎉 Done! Now run: python manage.py makemigrations && python manage.py migrate")
