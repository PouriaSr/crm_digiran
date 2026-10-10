from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Customer(models.Model):
    STATUS_CHOICES = [
        ('lead', 'بالقوه (لید)'),
        ('active', 'بالفعل (مشتری)'),
        ('inactive', 'غیرفعال'),
        ('lost', 'از دست رفته'),
    ]

    SOURCE_CHOICES = [
        ('website', 'وبسایت'),
        ('referral', 'معرفی مشتریان'),
        ('social', 'شبکه‌های اجتماعی'),
        ('direct', 'تماس مستقیم'),
        ('ads', 'تبلیغات'),
        ('other', 'سایر'),
    ]

    name = models.CharField('نام مشتری', max_length=200)
    mobile = models.CharField('شماره تماس', max_length=15, db_index=True)
    email = models.EmailField('ایمیل', blank=True, null=True)

    status = models.CharField('وضعیت', max_length=20,
                              choices=STATUS_CHOICES, default='lead', db_index=True)
    source = models.CharField('منبع جذب', max_length=20,
                              choices=SOURCE_CHOICES, default='direct')

    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name='customers',
                                    verbose_name='کارمند مسئول')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                   null=True, blank=True,
                                   related_name='created_customers',
                                   verbose_name='ایجادکننده')

    national_id = models.CharField('کد ملی', max_length=10, blank=True, null=True)
    birth_date = models.DateField('تاریخ تولد', blank=True, null=True)
    address = models.TextField('آدرس', blank=True, null=True)
    notes = models.TextField('یادداشت', blank=True, null=True)

    first_contact_date = models.DateTimeField('تاریخ اولین تماس', default=timezone.now)
    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)
    updated_at = models.DateTimeField('آخرین ویرایش', auto_now=True)

    class Meta:
        verbose_name = 'مشتری'
        verbose_name_plural = 'مشتریان'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.name} - {self.mobile}"

    @property
    def is_lead(self):
        return self.status == 'lead'