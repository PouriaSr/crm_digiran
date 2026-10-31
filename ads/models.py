from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from crm.source_snapshots import SourceSnapshotMixin


class AdPlatform(models.Model):
    """عنوان‌های تبلیغاتی (پلتفرم‌ها) — فقط ادمین می‌تواند اضافه/حذف کند"""
    name = models.CharField('عنوان', max_length=100, unique=True)
    ad_number_start = models.PositiveIntegerField(
        'شماره شروع آگهی',
        default=1000,
        help_text='اولین شناسه آگهی این پلتفرم — بعدی‌ها خودکار ادامه می‌یابند.',
    )
    is_active = models.BooleanField('فعال', default=True)
    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)

    class Meta:
        verbose_name = 'عنوان تبلیغاتی'
        verbose_name_plural = 'عنوان‌های تبلیغاتی'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_next_ad_number(self):
        """عدد بعدی سری برای این پلتفرم"""
        nums = []
        for n in self.ads.values_list('ad_number', flat=True):
            try:
                nums.append(int(n))
            except (ValueError, TypeError):
                continue
        if nums:
            return str(max(nums) + 1)
        return str(self.ad_number_start)


class AdProcess(models.Model):
    """فرآیند تبلیغ — هر فرآیند وابسته به یک پلتفرم + هزینه پیش‌فرض"""
    platform = models.ForeignKey(
        AdPlatform,
        on_delete=models.CASCADE,
        related_name='processes',
        verbose_name='عنوان',
    )
    name = models.CharField('نام فرآیند', max_length=150)
    default_cost = models.DecimalField(
        'هزینه پیش‌فرض (تومان)',
        max_digits=15,
        decimal_places=0,
        validators=[MinValueValidator(0)],
    )
    is_active = models.BooleanField('فعال', default=True)
    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)

    class Meta:
        verbose_name = 'فرآیند تبلیغ'
        verbose_name_plural = 'فرآیندهای تبلیغ'
        ordering = ['platform__name', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['platform', 'name'],
                name='unique_process_per_platform',
            ),
        ]

    def __str__(self):
        return f'{self.platform.name} — {self.name}'


class AdSource(models.Model):
    """منبع آگهی — شماره تماسی که آگهی با آن تعریف شده"""
    phone_number = models.CharField(
        'شماره تماس',
        max_length=20,
        unique=True,
        help_text='مثال: 09123456789',
    )
    label = models.CharField(
        'برچسب',
        max_length=100,
        blank=True,
        help_text='مثال: خط اصلی، خط پشتیبانی',
    )
    is_active = models.BooleanField('فعال', default=True)
    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)

    class Meta:
        verbose_name = 'منبع تبلیغ'
        verbose_name_plural = 'منابع تبلیغ'
        ordering = ['phone_number']

    def __str__(self):
        if self.label:
            return f'{self.phone_number} ({self.label})'
        return self.phone_number


class Ad(SourceSnapshotMixin):
    """رکورد اصلی تبلیغ"""
    platform = models.ForeignKey(
        AdPlatform,
        on_delete=models.PROTECT,
        related_name='ads',
        verbose_name='عنوان',
    )
    process = models.ForeignKey(
        AdProcess,
        on_delete=models.PROTECT,
        related_name='ads',
        verbose_name='فرآیند',
    )
    cost = models.DecimalField(
        'هزینه (تومان)',
        max_digits=15,
        decimal_places=0,
        help_text='به صورت خودکار از فرآیند پر می‌شود، قابل ویرایش است.',
    )
    source = models.ForeignKey(
        AdSource,
        on_delete=models.PROTECT,
        related_name='ads',
        verbose_name='منبع',
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='ads',
        verbose_name='محصول',
        null=True,
        blank=True,
    )
    ad_number = models.CharField(
        'شناسه آگهی',
        max_length=100,
        unique=True,
        help_text='شماره یونیک آگهی در پلتفرم',
    )
    note = models.TextField('توضیحات', blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='ads_created',
        verbose_name='کارشناس ثبت‌کننده',
    )
    created_at = models.DateTimeField('تاریخ ثبت', auto_now_add=True)

    class Meta:
        verbose_name = 'تبلیغ'
        verbose_name_plural = 'تبلیغات'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['created_by', '-created_at']),
        ]

    def __str__(self):
        return f'{self.platform.name} — {self.ad_number}'


class AdLog(models.Model):
    """تاریخچه کامل تغییرات — چه کسی، چه زمانی، چه تغییری

    ⭐ نکته طراحی (Fix #2):
    - `ad` با `on_delete=SET_NULL` تعریف شده تا با حذف Ad، لاگ‌ها زنده بمانند.
    - `ad_number_snapshot` شناسه‌ی خوانا را در خود لاگ نگه می‌دارد؛ پس از حذف
      Ad، هنوز می‌توان فهمید که این لاگ مربوط به کدام آگهی بوده.
    - `save()` به‌طور خودکار snapshot را از ad پر می‌کند؛ پس در views نیازی
      به تغییر کد نیست.
    """
    ACTION_CHOICES = [
        ('create', 'ایجاد'),
        ('update', 'ویرایش'),
        ('delete', 'حذف'),
    ]

    ad = models.ForeignKey(
        Ad,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
        verbose_name='تبلیغ',
    )
    # ⭐ اسنپ‌شات شناسه برای حفظ قابلیت audit پس از حذف Ad
    ad_number_snapshot = models.CharField(
        'شناسه آگهی (اسنپ‌شات)',
        max_length=100,
        blank=True,
        db_index=True,
        help_text='حفظ شناسه حتی پس از حذف رکورد اصلی',
    )
    action = models.CharField(
        'عملیات',
        max_length=10,
        choices=ACTION_CHOICES,
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='ad_logs',
        verbose_name='توسط',
    )
    changed_at = models.DateTimeField('زمان', default=timezone.now)
    changes = models.JSONField(
        'تغییرات',
        default=dict,
        blank=True,
        help_text='dict از {field: [old, new]}',
    )
    note = models.TextField('توضیح', blank=True)

    class Meta:
        verbose_name = 'تاریخچه تبلیغ'
        verbose_name_plural = 'تاریخچه تبلیغات'
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['ad', '-changed_at']),
            models.Index(fields=['ad_number_snapshot', '-changed_at']),
        ]

    def save(self, *args, **kwargs):
        # ⭐ Fix #2: پر کردن خودکار snapshot از ad (فقط یک‌بار، در اولین ذخیره)
        if not self.ad_number_snapshot and self.ad_id:
            try:
                self.ad_number_snapshot = self.ad.ad_number
            except Ad.DoesNotExist:
                # اگر Ad هنوز وجود ندارد (مثلاً batch insert)، بی‌صدا رد شو
                pass
        super().save(*args, **kwargs)

    @property
    def ad_label(self):
        """شناسه‌ی نمایشی — حتی اگر Ad حذف شده باشد کار می‌کند"""
        if self.ad_number_snapshot:
            return self.ad_number_snapshot
        if self.ad_id:
            return self.ad.ad_number
        return '—'

    def __str__(self):
        return f'{self.ad_label} — {self.get_action_display()}'
