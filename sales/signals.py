from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Invoice, InvoiceItem


def _recalc_invoice_totals(invoice_id):
    """محاسبه‌ی مجدد مبالغ فاکتور — با مقاومت در برابر حذف همزمان"""
    try:
        invoice = Invoice.objects.get(pk=invoice_id)
    except (Invoice.DoesNotExist, TypeError):
        return

    invoice.calculate_totals()
    invoice.save(update_fields=['subtotal', 'tax_amount', 'total', 'updated_at'])


@receiver(post_save, sender=InvoiceItem)
def recalc_on_item_save(sender, instance, **kwargs):
    """بعد از ذخیره‌ی هر قلم، مبالغ فاکتور رو دوباره حساب کن"""
    _recalc_invoice_totals(instance.invoice_id)


@receiver(post_delete, sender=InvoiceItem)
def recalc_on_item_delete(sender, instance, **kwargs):
    """بعد از حذف هر قلم، مبالغ فاکتور رو دوباره حساب کن"""
    _recalc_invoice_totals(instance.invoice_id)