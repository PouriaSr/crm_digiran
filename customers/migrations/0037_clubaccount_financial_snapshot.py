from django.db import migrations, models


def backfill_financial_snapshot(apps, schema_editor):
    ClubAccount = apps.get_model('customers', 'ClubAccount')
    for account in ClubAccount.objects.select_related('evaluation', 'loan_program', 'product').iterator():
        program = account.loan_program
        down = account.evaluation.proposed_down_payment
        if program.no_down_purchase_limit:
            usable = min(program.purchase_limit, program.no_down_purchase_limit + down)
            loan_purchase = max(0, usable - down)
        else:
            loan_purchase = program.purchase_limit
        difference = max(0, int(account.product.price) - (loan_purchase + down))
        account.loan_purchase_amount = loan_purchase
        account.down_payment_amount = down
        account.purchase_difference_amount = difference
        account.total_customer_payable = loan_purchase + down + difference + account.club_fee
        account.save(update_fields=[
            'loan_purchase_amount', 'down_payment_amount',
            'purchase_difference_amount', 'total_customer_payable',
        ])


class Migration(migrations.Migration):
    dependencies = [('customers', '0036_alter_clubpayment_payment_type')]

    operations = [
        migrations.AddField(
            model_name='clubaccount', name='loan_purchase_amount',
            field=models.PositiveBigIntegerField(default=0, verbose_name='سقف خرید وام تعلق‌گرفته'),
        ),
        migrations.AddField(
            model_name='clubaccount', name='down_payment_amount',
            field=models.PositiveBigIntegerField(default=0, verbose_name='پیش‌پرداخت قرارداد'),
        ),
        migrations.AddField(
            model_name='clubaccount', name='purchase_difference_amount',
            field=models.PositiveBigIntegerField(default=0, verbose_name='مابه‌التفاوت خرید'),
        ),
        migrations.AddField(
            model_name='clubaccount', name='total_customer_payable',
            field=models.PositiveBigIntegerField(default=0, verbose_name='جمع کل تعهد مشتری'),
        ),
        migrations.RunPython(backfill_financial_snapshot, migrations.RunPython.noop),
    ]
