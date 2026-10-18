from datetime import datetime, time
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
