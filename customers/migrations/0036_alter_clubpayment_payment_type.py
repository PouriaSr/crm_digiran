from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('customers', '0035_loan_guarantor_rank_rules')]

    operations = [
        migrations.AlterField(
            model_name='clubpayment',
            name='payment_type',
            field=models.CharField(
                choices=[
                    ('down_payment', 'پیش‌پرداخت'), ('installment', 'قسط'),
                    ('club_fee', 'هزینه باشگاه مشتریان'),
                    ('purchase_difference', 'مابه‌التفاوت خرید'),
                    ('purchase', 'پرداخت خرید'), ('other', 'سایر'),
                ],
                max_length=20,
                verbose_name='نوع پرداخت',
            ),
        ),
    ]
