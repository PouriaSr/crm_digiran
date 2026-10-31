from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from customers.models import Customer, CustomerCase
from crm.source_snapshots import SourceSnapshotMixin


# وضعیت مشتری که اپراتور در فرم ثبت تماس اعلام می‌کند (تک‌منبع حقیقت)
DECLARED_CUSTOMER_STATUS_CHOICES = [
    ('none', 'فاقد شرایط'),
    ('lead', 'بالقوه'),
    ('active', 'بالفعل'),
]


class Call(SourceSnapshotMixin):
    """مدل تماس — ثبت هر تماس تلفنی"""

    CALL_TYPE_CHOICES = [
        ('incoming', 'ورودی'),
        ('outgoing', 'خروجی'),
    ]

    CALL_STATUS_CHOICES = [
        ('answered', 'پاسخ داده شد'),
        ('missed', 'بی‌پاسخ'),
        ('busy', 'مشغول'),
        ('no_answer', 'جواب نداد'),
        ('followup', 'نیاز به پیگیری'),
    ]

    # نوع تماسی که کاربر در فرم «ثبت تماس» انتخاب می‌کند
    # (هم‌ارز HubCallForm.call_type — قبلاً ذخیره نمی‌شد و در call_type/status/purpose
    #  تجزیه می‌شد؛ حالا خودش نگه داشته می‌شود)
    CONTACT_TYPE_CHOICES = [
        ('incoming', 'تماس مشتری'),
        ('missed', 'از دست رفته'),
        ('divar', 'چت دیوار'),
        ('ads', 'تبلیغات'),
        ('followup', 'پیگیری'),
        ('busy', 'مشغول'),
    ]

    CALL_PURPOSE_CHOICES = [
        ('sale', 'فروش'),
        ('support', 'پشتیبانی'),
        ('followup', 'پیگیری'),
        ('complaint', 'شکایت'),
        ('info', 'اطلاعات'),
        ('other', 'سایر'),
    ]

    # ═══ ارتباط با مشتری ═══
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='calls',
        verbose_name='مشتری',
    )

    # ═══ اطلاعات تماس ═══
    caller_name = models.CharField('نام تماس‌گیرنده', max_length=200, db_index=True)
    call_number = models.CharField('شماره تماس', max_length=15, db_index=True)
    source = models.ForeignKey(
        'ads.AdSource', on_delete=models.PROTECT, null=True, blank=True,
        related_name='calls', verbose_name='منبع تماس',
    )

    # ═══ وضعیت و نوع ═══
    call_type = models.CharField('نوع تماس', max_length=20,
                                  choices=CALL_TYPE_CHOICES, default='outgoing')
    contact_type = models.CharField(
        'نوع تماس (فرم)', max_length=20,
        choices=CONTACT_TYPE_CHOICES, default='incoming', db_index=True,
    )
    declared_customer_status = models.CharField(
        'وضعیت اعلام‌شده مشتری', max_length=10,
        choices=DECLARED_CUSTOMER_STATUS_CHOICES,
        blank=True, default='', db_index=True,
        help_text='همان گزینه‌ای که اپراتور در فرم ثبت تماس انتخاب کرده',
    )
    status = models.CharField('وضعیت', max_length=20,
                               choices=CALL_STATUS_CHOICES, default='answered',
                               db_index=True)
    purpose = models.CharField('هدف تماس', max_length=20,
                                choices=CALL_PURPOSE_CHOICES, default='sale')

    requested_condition = models.CharField(
        'شرایط درخواستی', max_length=20,
        choices=CustomerCase.CONDITION_CHOICES, blank=True, default='',
    )
    send_address = models.BooleanField('درخواست ارسال آدرس', default=False)

    # ═══ زمان ═══
    call_date = models.DateTimeField('تاریخ تماس', default=timezone.now, db_index=True)
    duration = models.PositiveIntegerField('مدت تماس (دقیقه)', default=0)

    # ═══ پیگیری ═══
    follow_up_date = models.DateField('تاریخ پیگیری', null=True, blank=True)
    follow_up_time = models.TimeField('ساعت پیگیری', null=True, blank=True)
    is_followed_up = models.BooleanField('پیگیری شد؟', default=False)

    # ═══ توضیحات ═══
    notes = models.TextField('یادداشت', blank=True, null=True)

    # ═══ مسئول ═══
    called_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                   null=True, blank=True,
                                   related_name='calls',
                                   verbose_name='انجام‌دهنده')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name='created_calls',
                                    verbose_name='ایجادکننده')

    # ═══ زمان‌ها ═══
    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)
    updated_at = models.DateTimeField('آخرین ویرایش', auto_now=True)

    class Meta:
        verbose_name = 'تماس'
        verbose_name_plural = 'تماس‌ها'
        ordering = ['-call_date']
        indexes = [
            models.Index(fields=['-call_date']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.caller_name} - {self.call_number}"

    @property
    def duration_display(self):
        if self.duration == 0:
            return '—'
        if self.duration < 60:
            return f'{self.duration} دقیقه'
        hours = self.duration // 60
        mins = self.duration % 60
        if mins == 0:
            return f'{hours} ساعت'
        return f'{hours} ساعت و {mins} دقیقه'

    def save(self, *args, **kwargs):
        if self._state.adding and not self.source_id and self.customer_id:
            self.source_id = Customer.all_objects.filter(pk=self.customer_id).values_list('ad_source_id', flat=True).first()
        # ⭐ اگر «پیگیری انجام شده»، وضعیت نباید «نیاز به پیگیری» باشه
        if self.is_followed_up and self.status == 'followup':
            self.status = 'answered'

        # ⭐ اگر وضعیت «نیاز به پیگیری»، پیگیری نباید انجام‌شده باشه
        if self.status == 'followup':
            self.is_followed_up = False

        super().save(*args, **kwargs)
