from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from customers.models import Customer


class Call(models.Model):
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
    caller_name = models.CharField('نام تماس‌گیرنده', max_length=200)
    call_number = models.CharField('شماره تماس', max_length=15, db_index=True)

    # ═══ وضعیت و نوع ═══
    call_type = models.CharField('نوع تماس', max_length=20,
                                  choices=CALL_TYPE_CHOICES, default='outgoing')
    status = models.CharField('وضعیت', max_length=20,
                               choices=CALL_STATUS_CHOICES, default='answered',
                               db_index=True)
    purpose = models.CharField('هدف تماس', max_length=20,
                                choices=CALL_PURPOSE_CHOICES, default='sale')

    # ═══ زمان ═══
    call_date = models.DateTimeField('تاریخ تماس', default=timezone.now, db_index=True)
    duration = models.PositiveIntegerField('مدت تماس (دقیقه)', default=0)

    # ═══ پیگیری ═══
    follow_up_date = models.DateField('تاریخ پیگیری', null=True, blank=True)
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
        # ⭐ اگر «پیگیری انجام شده»، وضعیت نباید «نیاز به پیگیری» باشه
        if self.is_followed_up and self.status == 'followup':
            self.status = 'answered'

        # ⭐ اگر وضعیت «نیاز به پیگیری»، پیگیری نباید انجام‌شده باشه
        if self.status == 'followup':
            self.is_followed_up = False

        super().save(*args, **kwargs)