from django.db import migrations


def backfill(apps, schema_editor):
    """مشتریانی که پیگیری باز دارند → برچسب «بالقوه» و تیک نیاز به پیگیری"""
    Customer = apps.get_model('customers', 'Customer')
    Call = apps.get_model('calls', 'Call')

    ids = set(
        Call.objects
        .filter(is_followed_up=False, follow_up_date__isnull=False,
                customer__isnull=False)
        .values_list('customer_id', flat=True)
    )
    if not ids:
        return

    Customer.objects.filter(id__in=ids).update(stage='potential', needs_followup=True)


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0014_customer_needs_followup_customer_stage_and_more'),
        ('calls', '0007_call_declared_customer_status'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
