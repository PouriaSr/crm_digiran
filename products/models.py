from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone


class Product(models.Model):
    """مدل کالا — برای انبار و فاکتور"""

    UNIT_CHOICES = [
        ('عدد', 'عدد'),
        ('کیلوگرم', 'کیلوگرم'),
        ('گرم', 'گرم'),
        ('متر', 'متر'),
        ('لیتر', 'لیتر'),
        ('بسته', 'بسته'),
        ('جعبه', 'جعبه'),
    ]

    CATEGORY_CHOICES = [
        ('mobile', 'موبایل و تبلت'),
        ('laptop', 'لپ‌تاپ و کامپیوتر'),
        ('accessory', 'لوازم جانبی'),
        ('parts', 'قطعات'),
        ('service', 'خدمات'),
        ('other', 'سایر'),
    ]

    # ═══ اطلاعات اصلی ═══
    name = models.CharField('نام کالا', max_length=200, db_index=True)
    code = models.CharField('کد کالا (SKU)', max_length=50, unique=True, db_index=True)
    category = models.CharField('دسته‌بندی', max_length=20,
                                 choices=CATEGORY_CHOICES, default='other')
    unit = models.CharField('واحد', max_length=20,
                             choices=UNIT_CHOICES, default='عدد')

    # ═══ قیمت‌ها ═══
    price = models.DecimalField('قیمت فروش (تومان)', max_digits=15, decimal_places=0, default=0)
    cost_price = models.DecimalField('قیمت خرید (تومان)', max_digits=15, decimal_places=0,
                                      default=0, help_text='قیمت خرید از تامین‌کننده')

    # ═══ موجودی ═══
    stock = models.IntegerField('موجودی فعلی', default=0)
    min_stock = models.IntegerField('حداقل موجودی (هشدار)', default=0,
                                     help_text='اگه موجودی کمتر از این شد، هشدار بده')

    # ═══ اطلاعات تکمیلی ═══
    description = models.TextField('توضیحات', blank=True, null=True)
    is_active = models.BooleanField('فعال', default=True)

    # ═══ زمان‌ها ═══
    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)
    updated_at = models.DateTimeField('آخرین ویرایش', auto_now=True)

    class Meta:
        verbose_name = 'کالا'
        verbose_name_plural = 'کالاها'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def is_low_stock(self):
        """آیا موجودی کمتر از حد هشدار است؟"""
        return self.stock <= self.min_stock

    @property
    def stock_status(self):
        """وضعیت موجودی"""
        if self.stock == 0:
            return 'out'  # تمام شده
        elif self.stock <= self.min_stock:
            return 'low'  # کم
        return 'ok'  # مناسب

    @property
    def profit_margin(self):
        """حاشیه سود"""
        if self.cost_price and self.cost_price > 0:
            return round((float(self.price) - float(self.cost_price)) / float(self.cost_price) * 100, 1)
        return 0

    # ═══════════════════════════════════════════════════════════
    # مدیریت اتمیک موجودی
    # ═══════════════════════════════════════════════════════════
    def change_stock(self, quantity, movement_type, user=None,
                     reference_type='manual', reference_id=None,
                     reference_note=None, note=None):
        """
        تغییر اتمیک موجودی + ثبت لاگ گردش.

        Args:
            quantity: عدد صحیح. مثبت = افزایش، منفی = کاهش
            movement_type: یکی از StockMovement.MOVEMENT_TYPE_CHOICES
            user: کاربری که تغییر را انجام می‌دهد
            reference_type: 'invoice' / 'manual' / 'purchase' / 'return'
            reference_id: ID مرجع (مثلاً invoice.pk)
            reference_note: توضیح مرجع (مثلاً شماره فاکتور)
            note: توضیح آزاد

        Returns:
            موجودی جدید (int)

        Raises:
            ValueError: اگر quantity صحیح نباشد یا موجودی کافی نباشد
        """
        if not isinstance(quantity, int):
            raise ValueError('quantity باید عدد صحیح باشد')

        with transaction.atomic():
            # قفل روی ردیف برای جلوگیری از race condition
            locked = Product.objects.select_for_update().get(pk=self.pk)
            before = locked.stock
            after = before + quantity

            if after < 0:
                raise ValueError(
                    f'موجودی «{locked.name}» کافی نیست. '
                    f'موجودی فعلی: {before}، درخواستی: {abs(quantity)}'
                )

            locked.stock = after
            locked.save(update_fields=['stock', 'updated_at'])

            StockMovement.objects.create(
                product=locked,
                movement_type=movement_type,
                quantity=quantity,
                stock_before=before,
                stock_after=after,
                reference_type=reference_type,
                reference_id=reference_id,
                reference_note=reference_note,
                note=note,
                created_by=user,
            )

            # self رو هم هم‌گام کن تا توی همون request درست نمایش داده بشه
            self.stock = after
            return after


class StockMovement(models.Model):
    """لاگ گردش موجودی — هر تغییر موجودی یک رکورد می‌گیرد"""

    MOVEMENT_TYPE_CHOICES = [
        ('in', 'ورود'),           # خرید / برگشت از فروش
        ('out', 'خروج'),          # فروش
        ('adjust', 'تعدیل'),      # اصلاح دستی
        ('cancel', 'برگشت از لغو'),  # لغو فاکتور
    ]

    REFERENCE_TYPE_CHOICES = [
        ('invoice', 'فاکتور'),
        ('manual', 'دستی'),
        ('purchase', 'خرید'),
        ('return', 'برگشت'),
    ]

    product = models.ForeignKey(
        Product, on_delete=models.PROTECT,
        related_name='stock_movements', verbose_name='کالا'
    )
    movement_type = models.CharField(
        'نوع گردش', max_length=10,
        choices=MOVEMENT_TYPE_CHOICES, db_index=True
    )
    quantity = models.IntegerField('مقدار')  # مثبت = افزایش، منفی = کاهش
    stock_before = models.IntegerField('موجودی قبل')
    stock_after = models.IntegerField('موجودی بعد')

    reference_type = models.CharField(
        'مرجع', max_length=20,
        choices=REFERENCE_TYPE_CHOICES, default='manual'
    )
    reference_id = models.PositiveIntegerField('شناسه مرجع', null=True, blank=True)
    reference_note = models.CharField('توضیح مرجع', max_length=200, blank=True, null=True)

    note = models.TextField('یادداشت', blank=True, null=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stock_movements', verbose_name='ثبت‌کننده'
    )
    created_at = models.DateTimeField('تاریخ ثبت', auto_now_add=True)

    class Meta:
        verbose_name = 'گردش موجودی'
        verbose_name_plural = 'گردش‌های موجودی'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', '-created_at']),
            models.Index(fields=['reference_type', 'reference_id']),
        ]

    def __str__(self):
        sign = '+' if self.quantity >= 0 else ''
        return f"{self.product.code} — {self.get_movement_type_display()} {sign}{self.quantity}"

    @property
    def is_increase(self):
        """آیا این گردش باعث افزایش موجودی شده؟"""
        return self.quantity > 0

    @property
    def quantity_display(self):
        """نمایش مقدار با علامت"""
        return f'{self.quantity:+d}'