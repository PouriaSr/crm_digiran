from django.db import migrations, models


def backfill_contact_type(apps, schema_editor):
    """حدس نوع تماس برای رکوردهای قدیمی از روی داده‌های موجود"""
    Call = apps.get_model('calls', 'Call')
    for call in Call.objects.select_related('customer').all():
        t = 'incoming'
        if call.status == 'missed':
            t = 'missed'
        elif call.purpose == 'followup' or call.follow_up_date:
            t = 'followup'
        elif call.customer is not None and call.customer.ad_source_id:
            t = 'ads'
        if t != 'incoming':
            call.contact_type = t
            call.save(update_fields=['contact_type'])


class Migration(migrations.Migration):

    dependencies = [
        ('calls', '0004_alter_call_caller_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='call',
            name='contact_type',
            field=models.CharField(
                choices=[('incoming', 'تماس مشتری'), ('missed', 'از دست رفته'),
                         ('divar', 'چت دیوار'), ('ads', 'تبلیغات'),
                         ('followup', 'پیگیری')],
                db_index=True, default='incoming', max_length=20,
                verbose_name='نوع تماس (فرم)',
            ),
        ),
        migrations.RunPython(backfill_contact_type, migrations.RunPython.noop),
    ]
