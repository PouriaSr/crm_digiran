import secrets

from django.conf import settings
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from crm.private_files import ClubReceiptStorage, club_receipt_path


class LoanProgram(models.Model):
    PROVIDERS = [
        ('azki', 'ازکی'), ('gsm', 'جی‌اس‌ام'),
        ('setare_yek', 'ستاره یک'), ('wiki_pay', 'ویکی‌پی'),
    ]
    provider = models.CharField('وام', max_length=30, choices=PROVIDERS, db_index=True)
    term_months = models.PositiveSmallIntegerField('مدت (ماه)')
    credit_limit = models.PositiveBigIntegerField('مبلغ وام (تومان)')
    monthly_installment = models.PositiveBigIntegerField('قسط ماهانه (تومان)')
    purchase_limit = models.PositiveBigIntegerField('سقف خرید (تومان)')
    no_down_purchase_limit = models.PositiveBigIntegerField('سقف خرید بدون پیش‌پرداخت', default=0)
    down_payment = models.PositiveBigIntegerField('پیش‌پرداخت (تومان)', default=0)
    allowed_customer_ranks = models.JSONField('رتبه‌های مجاز متقاضی', default=list)
    allowed_guarantor_ranks = models.JSONField('رتبه‌های مجاز ضامن', default=list, blank=True)
    allowed_guarantor_ranks_for_b = models.JSONField(
        'رتبه‌های مجاز ضامن برای متقاضی B', default=list, blank=True,
        help_text='اگر خالی باشد همان فهرست عمومی ضامن استفاده می‌شود.',
    )
    allowed_jobs = models.JSONField(
        'شغل‌های مجاز متقاضی', default=list, blank=True,
        help_text='گزینه‌ها مستقیماً از فهرست شغل در تب پرونده خوانده می‌شوند؛ خالی یعنی بدون محدودیت.',
    )
    guarantee = models.CharField('ضمانت', max_length=250, blank=True)
    employment_note = models.CharField('مدرک شغلی', max_length=250, blank=True)
    is_active = models.BooleanField('فعال', default=True, db_index=True)
    order = models.PositiveSmallIntegerField('ترتیب', default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'provider', 'term_months', '-credit_limit']
        constraints = [models.UniqueConstraint(
            fields=['provider', 'term_months', 'credit_limit'], name='unique_active_loan_program_variant'
        )]
        verbose_name = 'طرح وام'
        verbose_name_plural = 'طرح‌های وام'

    def __str__(self):
        return f'{self.get_provider_display()} · {self.term_months} ماهه · {self.credit_limit:,} تومان'


class LoanEvaluation(models.Model):
    STATUS = [('ready', 'آماده انتخاب'), ('selected', 'انتخاب شده'), ('expired', 'منقضی')]
    reception = models.ForeignKey('customers.Reception', on_delete=models.CASCADE, related_name='loan_evaluations')
    case = models.ForeignKey('customers.CustomerCase', on_delete=models.CASCADE, related_name='loan_evaluations')
    requested_credit = models.PositiveBigIntegerField('رقم پیشنهادی وام')
    proposed_down_payment = models.PositiveBigIntegerField('مقدار پیش‌پرداخت')
    contract_number = models.CharField('شماره قرارداد', max_length=40, db_index=True, editable=False)
    result_program_ids = models.JSONField(default=list, editable=False)
    result_product_ids = models.JSONField(default=list, editable=False)
    snapshot = models.JSONField(default=dict, editable=False)
    status = models.CharField(max_length=12, choices=STATUS, default='ready', db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        verbose_name = 'ارزیابی وام'
        verbose_name_plural = 'ارزیابی‌های وام'


def contract_number():
    return f'DG-{timezone.localdate():%Y%m%d}-{secrets.token_hex(4).upper()}'


class ClubAccount(models.Model):
    DELIVERY_TYPES = [('instant', 'فوری'), ('delayed', 'چند روزه')]
    STATUS = [('active', 'فعال'), ('completed', 'تسویه شده'), ('cancelled', 'لغو شده')]
    customer = models.OneToOneField('customers.Customer', on_delete=models.PROTECT, related_name='club_account')
    reception = models.OneToOneField('customers.Reception', on_delete=models.PROTECT, related_name='club_account')
    evaluation = models.OneToOneField(LoanEvaluation, on_delete=models.PROTECT, related_name='club_account')
    contract_number = models.CharField('شماره قرارداد', max_length=40, unique=True, default=contract_number, editable=False)
    loan_program = models.ForeignKey(LoanProgram, on_delete=models.PROTECT, related_name='accounts')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='club_accounts')
    delivery_type = models.CharField('نوع تحویل', max_length=10, choices=DELIVERY_TYPES)
    panel_url = models.URLField('لینک پنل', max_length=500)
    customer_credit_rank = models.CharField('رتبه اعتباری مشتری', max_length=5)
    guarantor_name = models.CharField('نام ضامن', max_length=200, blank=True)
    guarantor_credit_rank = models.CharField('رتبه اعتباری ضامن', max_length=5, blank=True)
    guarantee_snapshot = models.CharField('ضمانت و مدارک', max_length=500, blank=True)
    club_fee = models.PositiveBigIntegerField('هزینه باشگاه مشتریان', default=0)
    loan_purchase_amount = models.PositiveBigIntegerField('سقف خرید وام تعلق‌گرفته', default=0)
    down_payment_amount = models.PositiveBigIntegerField('پیش‌پرداخت قرارداد', default=0)
    main_purchase_amount = models.PositiveBigIntegerField('خرید اصلی', default=0)
    purchase_difference_amount = models.BigIntegerField('مابه‌التفاوت خرید', default=0)
    total_customer_payable = models.PositiveBigIntegerField('مبلغ نهایی مشتری', default=0)
    status = models.CharField(max_length=12, choices=STATUS, default='active', db_index=True)
    selected_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-joined_at', '-pk']
        verbose_name = 'عضو باشگاه مشتریان'
        verbose_name_plural = 'باشگاه مشتریان'

    @property
    def panel_label(self):
        return 'پنل B2B' if self.delivery_type == 'instant' else 'پنل B2C'


class ClubPayment(models.Model):
    TYPES = [
        ('down_payment', 'پیش‌پرداخت'), ('installment', 'قسط'),
        ('club_fee', 'هزینه باشگاه مشتریان'),
        ('purchase_difference', 'مابه‌التفاوت خرید'),
        ('purchase', 'پرداخت خرید'), ('other', 'سایر'),
    ]
    STATUS = [('scheduled', 'برنامه‌ریزی شده'), ('paid', 'پرداخت شده'), ('overdue', 'معوق'), ('cancelled', 'لغو شده')]
    account = models.ForeignKey(ClubAccount, on_delete=models.CASCADE, related_name='payments')
    payment_type = models.CharField('نوع پرداخت', max_length=20, choices=TYPES)
    amount = models.PositiveBigIntegerField('مبلغ (تومان)', validators=[MinValueValidator(1)])
    due_date = models.DateField('سررسید', null=True, blank=True, db_index=True)
    paid_at = models.DateTimeField('زمان پرداخت', null=True, blank=True)
    status = models.CharField('وضعیت', max_length=12, choices=STATUS, default='scheduled', db_index=True)
    receipt = models.FileField(
        'رسید', storage=ClubReceiptStorage(), upload_to=club_receipt_path, max_length=255, blank=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'pdf'])],
    )
    receipt_name = models.CharField(max_length=200, blank=True)
    notes = models.TextField('توضیحات', blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-paid_at', 'due_date', '-pk']
        verbose_name = 'پرداخت باشگاه'
        verbose_name_plural = 'پرداخت‌های باشگاه'

    def save(self, *args, **kwargs):
        if self.status == 'paid' and not self.paid_at:
            self.paid_at = timezone.now()
        if self.receipt and not self.receipt_name:
            self.receipt_name = self.receipt.name.rsplit('/', 1)[-1][:200]
        super().save(*args, **kwargs)
