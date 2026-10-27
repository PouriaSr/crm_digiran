import jdatetime
import time
from django.db import models, transaction, IntegrityError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.utils import timezone
from customers.models import Customer
from products.models import Product


class Invoice(models.Model):
    """مدل فاکتور — سربرگ فاکتور"""

    STATUS_CHOICES = [
        ('draft', 'پیش‌نویس'),
        ('issued', 'صادر شده'),
        ('paid', 'پرداخت شده'),
        ('cancelled', 'لغو شده'),
    ]

    PAYMENT_TYPE_CHOICES = [
        ('cash', 'نقدی'),
        ('installment', 'اقساطی'),
        ('cheque', 'چکی'),
        ('card', 'کارت به کارت'),
        ('other', 'سایر'),
    ]

    # ═══ شماره و مشتری ═══
    number = models.CharField('شماره فاکتور', max_length=30, unique=True, db_index=True)
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT,
        related_name='invoices', verbose_name='مشتری'
    )

    # ═══ وضعیت ═══
    status = models.CharField('وضعیت', max_length=20,
                              choices=STATUS_CHOICES, default='draft', db_index=True)
    payment_type = models.CharField('نوع پرداخت', max_length=20,
                                     choices=PAYMENT_TYPE_CHOICES, default='cash')

    # ═══ تاریخ‌ها ═══
    issue_date = models.DateTimeField('تاریخ صدور', default=timezone.now, db_index=True)
    due_date = models.DateField('مهلت پرداخت', null=True, blank=True, db_index=True)

    # ═══ مالیات و تخفیف ═══
    discount = models.DecimalField('تخفیف (تومان)', max_digits=15, decimal_places=0,
                                   default=0, validators=[MinValueValidator(0)])
    tax_percent = models.DecimalField('درصد مالیات', max_digits=5, decimal_places=2,
                                      default=9, validators=[
                                          MinValueValidator(0), MaxValueValidator(100),
                                      ])
    tax_amount = models.DecimalField('مبلغ مالیات', max_digits=15, decimal_places=0, default=0)
    subtotal = models.DecimalField('جمع اقلام', max_digits=15, decimal_places=0,
                                   default=0, validators=[MinValueValidator(0)])
    total = models.DecimalField('مبلغ نهایی', max_digits=15, decimal_places=0, default=0, db_index=True)

    # ═══ توضیحات ═══
    notes = models.TextField('توضیحات', blank=True, null=True)

    # ═══ مسئول ═══
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_invoices', verbose_name='ایجادکننده'
    )

    # ═══ زمان‌ها ═══
    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)
    updated_at = models.DateTimeField('آخرین ویرایش', auto_now=True)

    class Meta:
        verbose_name = 'فاکتور'
        verbose_name_plural = 'فاکتورها'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'issue_date']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.number} - {self.customer.name}"

    def calculate_totals(self):
        """محاسبه جمع کل از روی اقلام"""
        items = self.items.all()
        subtotal = sum(item.total_price for item in items)

        self.subtotal = subtotal
        # تخفیف نباید بیشتر از جمع اقلام شود (وگرنه مبلغ نهایی منفی می‌شد)
        after_discount = subtotal - (self.discount or 0)
        if after_discount < 0:
            after_discount = 0

        tax = int(after_discount * (self.tax_percent or 0) / 100)
        if tax < 0:
            tax = 0

        self.tax_amount = tax
        self.total = after_discount + self.tax_amount
        return self.total

    def save(self, *args, **kwargs):
        # تولید شماره فاکتور خودکار — با تاریخ شمسی و ضد race condition
        if not self.number:
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        # قفل کردن آخرین رکورد برای محاسبه ID جدید
                        last = Invoice.objects.select_for_update().order_by('-id').first()
                        new_id = (last.id + 1) if last else 1
                        now_j = jdatetime.datetime.now()
                        self.number = f"INV-{now_j.year}{now_j.month:02d}-{new_id:04d}"
                        
                        # ذخیره در دیتابیس
                        super().save(*args, **kwargs)
                    return  # اگر موفق بود، از حلقه خارج شو
                except IntegrityError:
                    if attempt == max_retries - 1:
                        raise  # اگر بعد از ۵ بار باز هم خطا داد، خطا رو بفرست
                    
                    # ریست کردن مقادیر برای تلاش بعدی
                    self.pk = None
                    self.number = None
                    time.sleep(0.1)  # تاخیر خیلی کوتاه تا تراکنش دیگر تمام شود
        else:
            # اگر شماره از قبل وجود دارد، فقط ذخیره کن
            super().save(*args, **kwargs)

    @property
    def status_color(self):
        return {
            'draft': 'gray',
            'issued': 'blue',
            'paid': 'green',
            'cancelled': 'red',
        }.get(self.status, 'gray')

    @property
    def items_count(self):
        return self.items.count()


class InvoiceItem(models.Model):
    """قلم فاکتور — هر خط از فاکتور"""

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE,
        related_name='items', verbose_name='فاکتور'
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT,
        related_name='invoice_items', verbose_name='کالا'
    )

    quantity = models.PositiveIntegerField('تعداد', default=1)
    unit_price = models.DecimalField('قیمت واحد', max_digits=15, decimal_places=0,
                                     default=0, validators=[MinValueValidator(0)])
    total_price = models.DecimalField('جمع خط', max_digits=15, decimal_places=0, default=0)

    class Meta:
        verbose_name = 'قلم فاکتور'
        verbose_name_plural = 'اقلام فاکتور'

    def __str__(self):
        return f"{self.product.name} × {self.quantity}"

    def save(self, *args, **kwargs):
        # اگه قیمت واحد خالی بود، از قیمت کالا بگیر
        if not self.unit_price:
            self.unit_price = self.product.price

        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class InvoiceLog(models.Model):
    """لاگ تغییرات فاکتور — Audit Trail (۷.۹)"""

    ACTION_CREATED = 'created'
    ACTION_STATUS = 'status'
    ACTION_UPDATED = 'updated'
    ACTION_ITEM_ADDED = 'item_added'
    ACTION_ITEM_CHANGED = 'item_changed'
    ACTION_ITEM_REMOVED = 'item_removed'

    ACTION_CHOICES = [
        (ACTION_CREATED, 'صدور فاکتور'),
        (ACTION_STATUS, 'تغییر وضعیت'),
        (ACTION_UPDATED, 'ویرایش اطلاعات'),
        (ACTION_ITEM_ADDED, 'افزودن قلم'),
        (ACTION_ITEM_CHANGED, 'ویرایش قلم'),
        (ACTION_ITEM_REMOVED, 'حذف قلم'),
    ]

    ACTION_ICONS = {
        ACTION_CREATED: '📄',
        ACTION_STATUS: '🔄',
        ACTION_UPDATED: '✏️',
        ACTION_ITEM_ADDED: '➕',
        ACTION_ITEM_CHANGED: '📝',
        ACTION_ITEM_REMOVED: '➖',
    }

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE,
        related_name='logs', verbose_name='فاکتور'
    )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoice_logs', verbose_name='کاربر'
    )
    action = models.CharField(
        'رویداد', max_length=20,
        choices=ACTION_CHOICES, db_index=True,
    )
    field_name = models.CharField('نام فیلد', max_length=50, blank=True)
    old_value = models.TextField('مقدار قبلی', blank=True)
    new_value = models.TextField('مقدار جدید', blank=True)
    description = models.TextField('توضیحات')
    created_at = models.DateTimeField('تاریخ ثبت', auto_now_add=True)

    class Meta:
        verbose_name = 'لاگ فاکتور'
        verbose_name_plural = 'لاگ‌های فاکتور'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invoice', '-created_at']),
        ]

    def __str__(self):
        return f'{self.invoice.number} — {self.get_action_display()}'

    @property
    def user_display(self):
        if not self.user:
            return 'سیستم'
        return self.user.get_full_name() or self.user.username

    @property
    def icon(self):
        return self.ACTION_ICONS.get(self.action, '•')