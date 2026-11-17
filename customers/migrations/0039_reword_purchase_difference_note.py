from django.db import migrations


OLD_NOTE = 'مابه‌التفاوت خرید اصلی و قیمت گوشی؛ فاکتور یا رسید پرداخت را ثبت کنید.'
NEW_NOTE = 'رسید یا فاکتور پرداخت مابه‌التفاوت میان مبلغ خرید اصلی و قیمت گوشی را ثبت کنید.'


def update_notes(apps, schema_editor):
    payment = apps.get_model('customers', 'ClubPayment')
    payment.objects.using(schema_editor.connection.alias).filter(
        payment_type='purchase_difference', notes=OLD_NOTE,
    ).update(notes=NEW_NOTE)


def restore_notes(apps, schema_editor):
    payment = apps.get_model('customers', 'ClubPayment')
    payment.objects.using(schema_editor.connection.alias).filter(
        payment_type='purchase_difference', notes=NEW_NOTE,
    ).update(notes=OLD_NOTE)


class Migration(migrations.Migration):
    dependencies = [('customers', '0038_recalculate_club_financial_formula')]
    operations = [migrations.RunPython(update_notes, restore_notes)]
