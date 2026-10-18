from django.db import migrations


def backfill_snapshot(apps, schema_editor):
    """پر کردن ad_number_snapshot برای لاگ‌های موجود که ad دارند"""
    AdLog = apps.get_model('ads', 'AdLog')
    Ad = apps.get_model('ads', 'Ad')

    # فقط لاگ‌هایی که ad_id دارند ولی snapshot ندارند
    logs = AdLog.objects.filter(
        ad__isnull=False,
        ad_number_snapshot='',
    ).values_list('id', 'ad_id')

    # دیکشنری سریع ad_id → ad_number (فقط یک کوئری)
    ad_numbers = dict(Ad.objects.values_list('id', 'ad_number'))

    to_update = []
    for log_id, ad_id in logs:
        num = ad_numbers.get(ad_id, '')
        if num:
            to_update.append(AdLog(id=log_id, ad_number_snapshot=num))

    if to_update:
        AdLog.objects.bulk_update(
            to_update,
            fields=['ad_number_snapshot'],
            batch_size=500,
        )


class Migration(migrations.Migration):

    dependencies = [
        # اسم واقعی فایل 0003 — همون که Django خودش ساخت
        ('ads', '0003_adlog_ad_number_snapshot_alter_adlog_ad_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_snapshot, migrations.RunPython.noop),
    ]