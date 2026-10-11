from decimal import Decimal
from datetime import date, datetime

from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from crm.middleware import get_current_user
from .models import Invoice, InvoiceItem, InvoiceLog


# ═══════════════════════════════════════════════════════════
# محاسبه‌ی مجدد مبالغ (موجود)
# ═══════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════
# Audit Trail — ۷.۹
# ═══════════════════════════════════════════════════════════

# فیلدهایی که در فاکتور رصد می‌شن
TRACKED_INVOICE_FIELDS = {
    'status': 'وضعیت',
    'payment_type': 'نوع پرداخت',
    'discount': 'تخفیف',
    'tax_percent': 'درصد مالیات',
    'due_date': 'مهلت پرداخت',
    'issue_date': 'تاریخ صدور',
}

# فیلدهایی که saveهای داخلی (recalc) با update_fields می‌فرستن
_INTERNAL_UPDATE_FIELDS = {'subtotal', 'tax_amount', 'total', 'updated_at'}


# ═══════════════════════════════════════════════════════════
# مقایسه‌ی امن مقادیر — type-agnostic
# ═══════════════════════════════════════════════════════════

def _to_comparable(v):
    """
    تبدیل مقدار به یک شکل قابل مقایسه‌ی یکنواخت:
    - Decimal → normalize (9.00 → 9)
    - datetime → date ISO (چون فقط date-level comparison لازمه)
    - None → رشته‌ی خالی
    """
    if v is None:
        return ''
    if isinstance(v, Decimal):
        return str(v.normalize())
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def _values_equal(a, b):
    """آیا دو مقدار برابرن؟ (با نرمال‌سازی type)"""
    return _to_comparable(a) == _to_comparable(b)


def _format_value(field_name, value, instance):
    """نمایش خوانا از یک مقدار (choice fields رو به display تبدیل می‌کنه)"""
    if value is None or value == '':
        return '—'

    if field_name == 'status' and instance is not None:
        method = getattr(instance, 'get_status_display', None)
        if method:
            return str(method())

    if field_name == 'payment_type' and instance is not None:
        method = getattr(instance, 'get_payment_type_display', None)
        if method:
            return str(method())

    return str(value)


# ═══════════════════════════════════════════════════════════
# Invoice: pre_save — گرفتن state قدیمی
# ═══════════════════════════════════════════════════════════

@receiver(pre_save, sender=Invoice)
def capture_old_invoice_state(sender, instance, **kwargs):
    update_fields = kwargs.get('update_fields')

    # saveهای داخلی (recalc) رو نادیده بگیر
    if update_fields is not None and set(update_fields).issubset(_INTERNAL_UPDATE_FIELDS):
        instance._old_state = None
        return

    # ایجاد جدید — state قدیمی نداره
    if not instance.pk:
        instance._old_state = None
        return

    try:
        instance._old_state = Invoice.objects.get(pk=instance.pk)
    except Invoice.DoesNotExist:
        instance._old_state = None


# ═══════════════════════════════════════════════════════════
# Invoice: post_save — ثبت لاگ
# ═══════════════════════════════════════════════════════════

@receiver(post_save, sender=Invoice)
def log_invoice_save(sender, instance, created, **kwargs):
    update_fields = kwargs.get('update_fields')

    if update_fields is not None and set(update_fields).issubset(_INTERNAL_UPDATE_FIELDS):
        return

    user = get_current_user()

    # ─── ایجاد جدید ───
    if created:
        InvoiceLog.objects.create(
            invoice=instance,
            user=user,
            action=InvoiceLog.ACTION_CREATED,
            description=f'فاکتور «{instance.number}» صادر شد.',
        )
        return

    # ─── ویرایش — مقایسه با state قدیمی ───
    old = getattr(instance, '_old_state', None)
    if not old:
        return

    for field, label in TRACKED_INVOICE_FIELDS.items():
        old_val = getattr(old, field, None)
        new_val = getattr(instance, field, None)

        # ⭐ مقایسه‌ی امن با نرمال‌سازی type
        if _values_equal(old_val, new_val):
            continue

        old_display = _format_value(field, old_val, old)
        new_display = _format_value(field, new_val, instance)

        action = (
            InvoiceLog.ACTION_STATUS if field == 'status'
            else InvoiceLog.ACTION_UPDATED
        )

        InvoiceLog.objects.create(
            invoice=instance,
            user=user,
            action=action,
            field_name=field,
            old_value=_to_comparable(old_val),
            new_value=_to_comparable(new_val),
            description=f'{label}: {old_display} → {new_display}',
        )


# ═══════════════════════════════════════════════════════════
# InvoiceItem: pre_save — state قدیمی
# ═══════════════════════════════════════════════════════════

@receiver(pre_save, sender=InvoiceItem)
def capture_old_item_state(sender, instance, **kwargs):
    if not instance.pk:
        instance._old_state = None
        return
    try:
        instance._old_state = InvoiceItem.objects.get(pk=instance.pk)
    except InvoiceItem.DoesNotExist:
        instance._old_state = None


# ═══════════════════════════════════════════════════════════
# InvoiceItem: post_save — ثبت لاگ
# ═══════════════════════════════════════════════════════════

@receiver(post_save, sender=InvoiceItem)
def log_item_save(sender, instance, created, **kwargs):
    user = get_current_user()

    if created:
        InvoiceLog.objects.create(
            invoice=instance.invoice,
            user=user,
            action=InvoiceLog.ACTION_ITEM_ADDED,
            description=(
                f'کالای «{instance.product.name}» × {instance.quantity} افزوده شد.'
            ),
        )
        return

    old = getattr(instance, '_old_state', None)
    if not old:
        return

    changes = []
    if not _values_equal(old.quantity, instance.quantity):
        changes.append(f'تعداد {old.quantity} → {instance.quantity}')
    if not _values_equal(old.unit_price, instance.unit_price):
        old_price = old.unit_price or 0
        changes.append(
            f'قیمت واحد {old_price:,} → {instance.unit_price:,} تومان'
        )

    if not changes:
        return

    InvoiceLog.objects.create(
        invoice=instance.invoice,
        user=user,
        action=InvoiceLog.ACTION_ITEM_CHANGED,
        description=f'قلم «{instance.product.name}» ویرایش شد — ' + '، '.join(changes),
    )


# ═══════════════════════════════════════════════════════════
# InvoiceItem: post_delete — ثبت لاگ
# ═══════════════════════════════════════════════════════════

@receiver(post_delete, sender=InvoiceItem)
def log_item_delete(sender, instance, **kwargs):
    user = get_current_user()
    InvoiceLog.objects.create(
        invoice=instance.invoice,
        user=user,
        action=InvoiceLog.ACTION_ITEM_REMOVED,
        description=(
            f'کالای «{instance.product.name}» × {instance.quantity} حذف شد.'
        ),
    )