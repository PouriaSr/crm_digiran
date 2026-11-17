from django.db import migrations, models


def recalculate_signed_differences(apps, schema_editor):
    ClubAccount = apps.get_model('customers', 'ClubAccount')
    ClubPayment = apps.get_model('customers', 'ClubPayment')
    for account in ClubAccount.objects.select_related('product').iterator():
        difference = account.main_purchase_amount - int(account.product.price)
        account.purchase_difference_amount = difference
        account.total_customer_payable = account.main_purchase_amount - difference + account.club_fee
        account.save(update_fields=['purchase_difference_amount', 'total_customer_payable'])
        if difference <= 0:
            ClubPayment.objects.filter(
                account_id=account.pk,
                payment_type='purchase_difference',
                status__in=('scheduled', 'overdue'),
                receipt='',
            ).delete()


class Migration(migrations.Migration):
    dependencies = [('customers', '0039_reword_purchase_difference_note')]

    operations = [
        migrations.AddField(
            model_name='loanprogram',
            name='allowed_jobs',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='گزینه‌ها مستقیماً از فهرست شغل در تب پرونده خوانده می‌شوند؛ خالی یعنی بدون محدودیت.',
                verbose_name='شغل‌های مجاز متقاضی',
            ),
        ),
        migrations.AlterField(
            model_name='clubaccount',
            name='purchase_difference_amount',
            field=models.BigIntegerField(default=0, verbose_name='مابه‌التفاوت خرید'),
        ),
        migrations.RunPython(recalculate_signed_differences, migrations.RunPython.noop),
    ]
