import crm.private_files
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('ads', '0008_ad_platform_name_snapshot_ad_process_name_snapshot'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='ad', name='payment_receipt',
            field=models.FileField(
                blank=True, max_length=255, storage=crm.private_files.AdReceiptStorage(),
                upload_to=crm.private_files.ad_receipt_path, verbose_name='فاکتور یا رسید پرداخت',
            ),
        ),
        migrations.AddField(
            model_name='ad', name='payment_receipt_name',
            field=models.CharField(blank=True, editable=False, max_length=200),
        ),
        migrations.AddField(
            model_name='ad', name='payment_note',
            field=models.TextField(blank=True, verbose_name='توضیحات پرداخت'),
        ),
        migrations.AddField(
            model_name='ad', name='payment_registered_at',
            field=models.DateTimeField(blank=True, editable=False, null=True, verbose_name='زمان ثبت پرداخت'),
        ),
        migrations.AddField(
            model_name='ad', name='payment_registered_by',
            field=models.ForeignKey(
                blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='ad_payments_registered', to=settings.AUTH_USER_MODEL,
                verbose_name='ثبت‌کننده پرداخت',
            ),
        ),
    ]
