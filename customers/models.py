from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class CustomerManager(models.Manager):
    """مدیر پیش‌فرض — فقط مشتریان فعال"""
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Customer(models.Model):
    CUSTOMER_TYPE_CHOICES = [
        ('none', 'فاقد شرایط'),
        ('cash', 'نقدی'),
        ('cheque', 'چک'),
        ('installment', 'قسطی'),
    ]
    customer_type = models.CharField('نوع مشتری', max_length=20, choices=CUSTOMER_TYPE_CHOICES, default='none')
    cheques_count = models.PositiveSmallIntegerField('تعداد چک', null=True, blank=True)
    installments_count = models.PositiveSmallIntegerField('تعداد اقساط', null=True, blank=True)

    STATUS_CHOICES = [
        ('lead', 'بالقوه (لید)'),
        ('active', 'بالفعل (مشتری)'),
        ('inactive', 'غیرفعال'),
        ('lost', 'از دست رفته'),
    ]

    SOURCE_CHOICES = [
        ('website', 'سایت'),
        ('social', 'شبکه‌های اجتماعی'),
        ('referral', 'معرفی مشتریان'),
        ('ads', 'تماس از طریق تبلیغات'),
        ('direct', 'تماس مستقیم'),
        ('other', 'سایر'),
]

    name = models.CharField('نام مشتری', max_length=200, db_index=True)
    mobile = models.CharField('شماره تماس', max_length=15, db_index=True)
    email = models.EmailField('ایمیل', blank=True, null=True)

    status = models.CharField('وضعیت', max_length=20,
                              choices=STATUS_CHOICES, default='lead', db_index=True)
    source = models.CharField('منبع جذب', max_length=20,
                              choices=SOURCE_CHOICES, default='website')
    ad_source = models.ForeignKey('ads.AdSource', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='منبع آگهی')

    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name='customers',
                                    verbose_name='کارمند مسئول')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                   null=True, blank=True,
                                   related_name='created_customers',
                                   verbose_name='ایجادکننده')

    national_id = models.CharField('کد ملی', max_length=10, blank=True, null=True, db_index=True)
    birth_date = models.DateField('تاریخ تولد', blank=True, null=True)
    address = models.TextField('آدرس', blank=True, null=True)
    notes = models.TextField('یادداشت قدیمی', blank=True, null=True,
                              help_text='فیلد قدیمی — تدریجاً به CustomerNote منتقل شود')

    first_contact_date = models.DateTimeField('تاریخ اولین تماس', default=timezone.now)
    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)
    updated_at = models.DateTimeField('آخرین ویرایش', auto_now=True)

    # ═══ Soft Delete (غیرفعال‌سازی) ═══
    is_deleted = models.BooleanField('غیرفعال‌شده', default=False, db_index=True)
    deleted_at = models.DateTimeField('تاریخ غیرفعال‌سازی', null=True, blank=True)

    objects = CustomerManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = 'مشتری'
        verbose_name_plural = 'مشتریان'
        ordering = ['-created_at']
        base_manager_name = 'all_objects'
        default_manager_name = 'objects'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['source']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.name} - {self.mobile}"

    @property
    def is_lead(self):
        return self.status == 'lead'

    @property
    def notes_count(self):
        """تعداد یادداشت‌های جدید"""
        return self.notes_new.count()

    @property
    def last_note(self):
        """آخرین یادداشت"""
        return self.notes_new.first()

    def delete(self, using=None, keep_parents=False):
        """غیرفعال‌سازی (Soft Delete)"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])

    def hard_delete(self):
        """حذف کامل — با احتیاط"""
        return super().delete()

    def restore(self):
        """بازگردانی به لیست فعال"""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])


class CustomerNote(models.Model):
    """یادداشت مشتری — هر یادداشت یک رکورد جدا با نویسنده و تاریخ"""

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE,
        related_name='notes_new', verbose_name='مشتری'
    )
    text = models.TextField('متن یادداشت')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='customer_notes', verbose_name='نویسنده'
    )
    is_pinned = models.BooleanField('سنجاق‌شده', default=False,
                                     help_text='یادداشت‌های سنجاق‌شده بالای لیست نمایش داده می‌شوند')
    created_at = models.DateTimeField('تاریخ ثبت', auto_now_add=True)
    updated_at = models.DateTimeField('آخرین ویرایش', auto_now=True)

    class Meta:
        verbose_name = 'یادداشت مشتری'
        verbose_name_plural = 'یادداشت‌های مشتری'
        ordering = ['-is_pinned', '-created_at']
        indexes = [
            models.Index(fields=['customer', '-created_at']),
        ]

    def __str__(self):
        preview = self.text[:50] if self.text else ''
        return f"{self.customer.name} — {preview}"

    @property
    def author_name(self):
        if not self.created_by:
            return 'حذف‌شده'
        return self.created_by.get_full_name() or self.created_by.username

    def can_edit(self, user):
        """فقط نویسنده یا سوپریوزر می‌تواند ویرایش/حذف کند"""
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return self.created_by_id == user.id

class Visit(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='visits', verbose_name='مشتری')
    visit_date = models.DateTimeField('تاریخ مراجعه', default=timezone.now)
    is_successful = models.BooleanField('مراحل با موفقیت طی شد؟', default=False)
    notes = models.TextField('یادداشت', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='ثبت‌کننده')
    created_at = models.DateTimeField('تاریخ ثبت', auto_now_add=True)

    class Meta:
        verbose_name = 'مراجعه حضوری'
        verbose_name_plural = 'مراجعات حضوری'
        ordering = ['-visit_date']

    def __str__(self):
        return f"{self.customer.name} - {self.visit_date.strftime('%Y/%m/%d')}"
