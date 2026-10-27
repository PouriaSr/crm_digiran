from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class CustomerManager(models.Manager):
    """مدیر پیش‌فرض — فقط مشتریان فعال"""
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Customer(models.Model):
    # is_lead یک property است (پایین‌تر) — فیلد جداگانه لازم نیست
    CUSTOMER_TYPE_CHOICES = [
        ('none', 'فاقد شرایط'),
        ('cash', 'نقدی'),
        ('cheque', 'چک'),
        ('installment', 'قسطی'),
    ]
    customer_type = models.CharField('نوع مشتری', max_length=20, choices=CUSTOMER_TYPE_CHOICES, default='none')
    cheques_count = models.PositiveSmallIntegerField('تعداد چک', null=True, blank=True)
    installments_count = models.PositiveSmallIntegerField('تعداد اقساط', null=True, blank=True)

    # برچسب مرحله‌ای (خارج از وضعیت فعلی)
    STAGE_CHOICES = [
        ('lead', 'سرنخ'),
        ('potential', 'بالقوه'),
    ]

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
        ('divar', 'چت دیوار'),
        ('direct', 'تماس مستقیم'),
        ('other', 'سایر'),
]

    stage = models.CharField('برچسب', max_length=20, choices=STAGE_CHOICES,
                             default='lead', db_index=True)
    needs_followup = models.BooleanField('نیاز به پیگیری', default=False, db_index=True)
    # مصاحبه‌کننده (از سؤال ۱ تب پذیرش) — از تب‌های مشتریان مخفی می‌شود
    is_interviewer = models.BooleanField('مصاحبه‌کننده', default=False, db_index=True)

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
    notes = models.TextField('شرح مکالمه', blank=True, null=True,
                              help_text='شرح آخرین مکالمه با مشتری')

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


# ═══════════════════════════════════════════════════════════════
# پذیرش حضوری (تب دوم مرکز مشتریان)
# ═══════════════════════════════════════════════════════════════
class Reception(models.Model):
    """پذیرش یک مراجعه‌ی حضوری + تایمر انتظار"""

    PERSON_CHOICES = [
        ('customer', 'مشتری'),
        ('interviewer', 'مصاحبه‌کننده'),
    ]
    VISIT_CHOICES = [
        ('yes', 'بله'),
        ('no', 'خیر'),
    ]
    WAIT_CHOICES = [
        ('0', 'به تازگی (۰ دقیقه)'),
        ('30', '۳۰ دقیقه'),
        ('45', '۴۵ دقیقه'),
        ('60', '۱ ساعت'),
        ('more', 'بیشتر از یک ساعت'),
    ]
    WAIT_OFFSET_MINUTES = {'0': 0, '30': 30, '45': 45, '60': 60, 'more': 90}

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE,
        related_name='receptions', verbose_name='مشتری',
    )

    person_type = models.CharField('فرد مورد نظر', max_length=20,
                                   choices=PERSON_CHOICES, blank=True)
    has_visit = models.CharField('مراجعه حضوری دارد؟', max_length=5,
                                 choices=VISIT_CHOICES, blank=True)
    wait_choice = models.CharField('مدت انتظار', max_length=10,
                                   choices=WAIT_CHOICES, blank=True)

    wait_started_at = models.DateTimeField('شروع انتظار', null=True, blank=True)
    wait_ended_at = models.DateTimeField('پایان انتظار', null=True, blank=True)
    wait_minutes_total = models.PositiveIntegerField('مجموع انتظار (دقیقه)', null=True, blank=True)
    is_waiting = models.BooleanField('در حال انتظار', default=False)

    # شرط فعال شدن «ثبت اطلاعات مشتری»
    info_submitted = models.BooleanField('اطلاعات مشتری ثبت شد', default=False)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='receptions_created', verbose_name='ثبت‌کننده',
    )
    created_at = models.DateTimeField('تاریخ ثبت', auto_now_add=True)
    updated_at = models.DateTimeField('آخرین ویرایش', auto_now=True)

    class Meta:
        verbose_name = 'پذیرش حضوری'
        verbose_name_plural = 'پذیرش‌های حضوری'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.customer.name} — {self.get_wait_choice_display() or "بدون انتظار"}'

    @property
    def answers_complete(self):
        return bool(self.person_type and self.has_visit and self.wait_choice)

    @property
    def can_submit_info(self):
        """دکمه‌ی «ثبت اطلاعات مشتری» چه زمانی فعال شود"""
        return self.answers_complete and self.customer.stage == 'potential'


# ═══════════════════════════════════════════════════════════════
# پرونده مشتری (تب سوم)
# ═══════════════════════════════════════════════════════════════

class FollowUp(models.Model):
    """
    یک «پیگیری» با تاریخ سررسید.
      • is_done=False → پیگیری باز (باید انجام شود)
      • is_done=True  → نتیجه ثبت شده
    ثبت «تماس پیگیری» پیگیری باز را می‌بندد و اگر تیک «نیاز به پیگیری جدید»
    بخورد، یک پیگیری باز تازه با تاریخ جدید ساخته می‌شود.
    """
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE, related_name='followups',
        verbose_name='مشتری',
    )
    due_date = models.DateField('تاریخ پیگیری')
    note = models.TextField('شرح پیگیری', blank=True)
    is_done = models.BooleanField('انجام شد', default=False, db_index=True)
    done_at = models.DateTimeField('زمان ثبت نتیجه', null=True, blank=True)
    done_note = models.TextField('نتیجه پیگیری', blank=True)
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='followups_created', verbose_name='ثبت‌کننده',
    )
    created_at = models.DateTimeField('تاریخ ثبت', auto_now_add=True)

    class Meta:
        verbose_name = 'پیگیری'
        verbose_name_plural = 'پیگیری‌ها'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'is_done']),
        ]

    def __str__(self):
        state = 'انجام‌شده' if self.is_done else 'باز'
        return f'پیگیری {self.customer.name} — {self.due_date} ({state})'


class RecordUpdate(models.Model):
    """
    دفتر تغییرات اطلاعات تب‌های «پذیرش» و «پرونده».
    هر ویرایش یک رکورد با فهرست تغییرات (چه فیلدی، از چه، به چه) می‌سازد.
    """
    SCOPE_CHOICES = [
        ('reception', 'پذیرش'),
        ('case', 'پرونده'),
    ]

    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE, related_name='record_updates',
        verbose_name='مشتری',
    )
    scope = models.CharField('تب', max_length=20, choices=SCOPE_CHOICES, db_index=True)
    changes = models.JSONField('تغییرات', default=list)
    edited_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='record_updates_done', verbose_name='ویرایش‌کننده',
    )
    created_at = models.DateTimeField('زمان', auto_now_add=True)

    class Meta:
        verbose_name = 'تغییر اطلاعات'
        verbose_name_plural = 'تغییرات اطلاعات'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['scope', 'customer'])]

    def __str__(self):
        return f'{self.get_scope_display()} — {self.customer.name}'

class CustomerCase(models.Model):
    """پرونده‌ی مشتری — شرایط، شغل، اعتبار، وام‌ها، کالا و نتیجه‌ی مراجعه"""

    CONDITION_CHOICES = [
        ('cheque', 'چکی'),
        ('retired', 'بازنشسته'),
        ('cash', 'نقد'),
        ('credit', 'دارای اعتبار'),
        ('other', 'سایر'),
    ]
    CHEQUE_OWNER_CHOICES = [
        ('self', 'برای خودش'),
        ('other', 'برای دیگری'),
    ]
    JOB_CHOICES = [
        ('government', 'کارمند دولتی'),
        ('private', 'کارمند خصوصی'),
        ('retired', 'بازنشسته'),
        ('freelance', 'آزاد'),
        ('unemployed', 'خانه‌دار/بیکار'),
    ]
    CREDIT_RANK_CHOICES = [
        ('A1', 'A1'), ('A2', 'A2'), ('A3', 'A3'),
        ('B1', 'B1'), ('B2', 'B2'), ('B3', 'B3'),
        ('C1', 'C1'), ('C2', 'C2'), ('C3', 'C3'),
        ('D1', 'D1'), ('D2', 'D2'), ('D3', 'D3'),
        ('E1', 'E1'), ('E2', 'E2'), ('E3', 'E3'),
    ]
    LOAN_CHOICES = [
        ('azki', 'ازکی'),
        ('mehrabani', 'مهربانی'),
        ('bajat', 'باجت'),
        ('refah', 'کارت رفاه'),
        ('kalapi', 'کالاپی'),
        ('tara', 'تارا'),
        ('manisa', 'مانیسا'),
        ('digipay', 'دیجی‌پی'),
        ('gsm', 'جی‌اس‌ام'),
    ]
    RESULT_CHOICES = [
        ('bought', 'خرید کرد'),
        ('abandoned', 'منصرف شد'),
        ('review', 'در حال بررسی'),
    ]

    customer = models.OneToOneField(
        Customer, on_delete=models.CASCADE,
        related_name='case', verbose_name='مشتری',
    )

    condition = models.CharField('شرایط', max_length=20, choices=CONDITION_CHOICES, blank=True)
    cheque_owner = models.CharField('چک برای', max_length=10,
                                    choices=CHEQUE_OWNER_CHOICES, blank=True)
    cheque_other_name = models.CharField('نام صاحب چک', max_length=200, blank=True)
    cheque_other_phone = models.CharField('شماره تماس صاحب چک', max_length=15, blank=True)

    job = models.CharField('شغل', max_length=20, choices=JOB_CHOICES, blank=True)
    credit_rank = models.CharField('رتبه اعتباری', max_length=5,
                                   choices=CREDIT_RANK_CHOICES, blank=True)
    active_loans = models.JSONField('وام‌های فعال', default=list, blank=True)

    product = models.ForeignKey(
        'products.Product', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cases', verbose_name='کالا',
    )
    quantity = models.PositiveIntegerField('تعداد', default=1)

    visit_result = models.CharField('نتیجه مراجعه', max_length=20,
                                    choices=RESULT_CHOICES, blank=True)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cases_created', verbose_name='ثبت‌کننده',
    )
    created_at = models.DateTimeField('تاریخ ثبت', auto_now_add=True)
    updated_at = models.DateTimeField('آخرین ویرایش', auto_now=True)

    class Meta:
        verbose_name = 'پرونده مشتری'
        verbose_name_plural = 'پرونده‌های مشتری'
        ordering = ['-created_at']

    def __str__(self):
        return f'پرونده {self.customer.name}'

    @property
    def loans_display(self):
        labels = dict(self.LOAN_CHOICES)
        return '، '.join(labels.get(x, x) for x in (self.active_loans or []))
