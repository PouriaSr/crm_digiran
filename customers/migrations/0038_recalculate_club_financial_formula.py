from datetime import date

from django.db import migrations, models


def recalculate_financial_snapshot(apps, schema_editor):
    ClubAccount = apps.get_model('customers', 'ClubAccount')
    ClubPayment = apps.get_model('customers', 'ClubPayment')
    for account in ClubAccount.objects.select_related('evaluation', 'loan_program', 'product').iterator():
        loan_purchase = account.loan_program.purchase_limit
        down = account.evaluation.proposed_down_payment
        main_purchase = loan_purchase + down
        difference = max(0, main_purchase - int(account.product.price))
        account.loan_purchase_amount = loan_purchase
        account.down_payment_amount = down
        account.main_purchase_amount = main_purchase
        account.purchase_difference_amount = difference
        account.total_customer_payable = main_purchase - difference + account.club_fee
        account.save(update_fields=[
            'loan_purchase_amount', 'down_payment_amount', 'main_purchase_amount',
            'purchase_difference_amount', 'total_customer_payable',
        ])
        editable = ClubPayment.objects.filter(
            account_id=account.pk, payment_type='purchase_difference',
            status='scheduled', receipt='',
        ).order_by('pk')
        first = editable.first()
        if difference:
            if first:
                first.amount = difference
                first.notes = 'مابه‌التفاوت خرید اصلی و قیمت گوشی؛ فاکتور یا رسید پرداخت را ثبت کنید.'
                first.save(update_fields=['amount', 'notes'])
                editable.exclude(pk=first.pk).delete()
            elif not ClubPayment.objects.filter(
                    account_id=account.pk, payment_type='purchase_difference').exists():
                ClubPayment.objects.create(
                    account_id=account.pk, payment_type='purchase_difference',
                    amount=difference, due_date=date.today(), status='scheduled',
                    created_by_id=account.selected_by_id,
                    notes='مابه‌التفاوت خرید اصلی و قیمت گوشی؛ فاکتور یا رسید پرداخت را ثبت کنید.',
                )
        else:
            editable.delete()


class Migration(migrations.Migration):
    dependencies = [('customers', '0037_clubaccount_financial_snapshot')]

    operations = [
        migrations.AddField(
            model_name='clubaccount', name='main_purchase_amount',
            field=models.PositiveBigIntegerField(default=0, verbose_name='خرید اصلی'),
        ),
        migrations.AlterField(
            model_name='clubaccount', name='total_customer_payable',
            field=models.PositiveBigIntegerField(default=0, verbose_name='مبلغ نهایی مشتری'),
        ),
        migrations.AlterField(
            model_name='clubpayment', name='status',
            field=models.CharField(
                choices=[('scheduled', 'برنامه‌ریزی شده'), ('paid', 'پرداخت شده'),
                         ('overdue', 'معوق'), ('cancelled', 'لغو شده')],
                db_index=True, default='scheduled', max_length=12, verbose_name='وضعیت',
            ),
        ),
        migrations.RunPython(recalculate_financial_snapshot, migrations.RunPython.noop),
    ]
