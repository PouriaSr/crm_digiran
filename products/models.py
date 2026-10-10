from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone


class Category(models.Model):
    """دسته‌بندی کالا — قابل مدیریت از پنل ادمین"""

    name = models.CharField('نام دسته', max_length=100)
    slug = models.SlugField(
        'نام کوتاه (انگلیسی)', max_length=50, unique=True,
        help_text='مثلاً: mobile, laptop — فقط حروف انگلیسی، اعداد، - و _'
    )
    icon = models.CharField(
        'آیکون (ایموجی)', max_length=10, blank=True,
        help_text='مثلاً: 📱 💻 🎧'
    )
    description = models.TextField('توضیحات', blank=True, null=True)
    order = models.PositiveIntegerField(
        'ترتیب نمایش', default=0,
        help_text='عدد کمتر = بالاتر'
    )
    is_active = models.BooleanField('فعال', default=True)
    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)
    updated_at = models.DateTimeField('آخرین ویرایش', auto_now=True)

    class Meta:
        verbose_name = 'دسته‌بندی'
        verbose_name_plural = 'دسته‌بندی‌ها'
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active', 'order']),
        ]

    def __str__(self):
        return f'{self.icon} {self.name}'.strip()

    @property
    def products_count(self):
        # اگه از annotate اومده باشه، ازش بخون؛ وگرنه fallback
        if hasattr(self, '_products_count'):
            return self._products_count
        return self.products.count()


class ProductManager(models.Manager):
    """مدیر پیش‌فرض — فقط محصولات حذف‌نشده"""
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


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

    # ═══ اطلاعات اصلی ═══
    name = models.CharField('نام کالا', max_length=200, db_index=True)
    code = models.CharField('کد کالا (SKU)', max_length=50, unique=True, db_index=True)

    category = models.ForeignKey(
        Category, on_delete=models.PROTECT,
        related_name='products', verbose_name='دسته‌بندی',
    )

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

    # ═══ Soft Delete ═══
    is_deleted = models.BooleanField('حذف‌شده', default=False, db_index=True)
    deleted_at = models.DateTimeField('تاریخ حذف', null=True, blank=True)

    # ═══ زمان‌ها ═══
    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)
    updated_at = models.DateTimeField('آخرین ویرایش', auto_now=True)

    # ═══ مدیرها ═══
    objects = ProductManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = 'کالا'
        verbose_name_plural = 'کالاها'
        ordering = ['-created_at']
        base_manager_name = 'all_objects'
        default_manager_name = 'objects'
        indexes = [
            models.Index(fields=['code']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def is_low_stock(self):
        return self.stock <= self.min_stock

    @property
    def stock_status(self):
        if self.stock == 0:
            return 'out'
        elif self.stock <= self.min_stock:
            return 'low'
        return 'ok'

    @property
    def profit_margin(self):
        if self.cost_price and self.cost_price > 0:
            return round((float(self.price) - float(self.cost_price)) / float(self.cost_price) * 100, 1)
        return 0

    @property
    def is_used(self):
        return self.invoice_items.exists() or self.stock_movements.exists()

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=['is_deleted', 'deleted_at', 'is_active', 'updated_at'])

    def hard_delete(self):
        return super().delete()

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.is_active = True
        self.save(update_fields=['is_deleted', 'deleted_at', 'is_active', 'updated_at'])

    def change_stock(self, quantity, movement_type, user=None,
                     reference_type='manual', reference_id=None,
                     reference_note=None, note=None):
        if not isinstance(quantity, int):
            raise ValueError('quantity باید عدد صحیح باشد')

        with transaction.atomic():
            locked = Product.all_objects.select_for_update().get(pk=self.pk)
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

            self.stock = after
            return after


class StockMovement(models.Model):
    """لاگ گردش موجودی"""

    MOVEMENT_TYPE_CHOICES = [
        ('in', 'ورود'),
        ('out', 'خروج'),
        ('adjust', 'تعدیل'),
        ('cancel', 'برگشت از لغو'),
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
    quantity = models.IntegerField('مقدار')
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
        return self.quantity > 0

    @property
    def quantity_display(self):
        return f'{self.quantity:+d}'