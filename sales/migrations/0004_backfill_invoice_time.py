from datetime import datetime, time
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
