from django.conf import settings
from django.db import models
from django.utils import timezone

from crm.private_files import HiringDocumentStorage, resume_path


class CaseWorkSession(models.Model):
    reception = models.ForeignKey('customers.Reception', on_delete=models.CASCADE, related_name='work_sessions')
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    started_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    ended_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['-started_at', '-pk']
        constraints = [models.UniqueConstraint(fields=['reception'], condition=models.Q(ended_at__isnull=True), name='one_active_case_work_session')]

    @property
    def seconds(self):
        return max(0, int(((self.ended_at or timezone.now()) - self.started_at).total_seconds()))

    @property
    def minutes(self):
        return round(self.seconds / 60, 1)


class HiringAdSequence(models.Model):
    platform = models.CharField(max_length=20, unique=True)
    next_number = models.PositiveIntegerField()


class HiringAd(models.Model):
    PLATFORMS = [('jobvision', 'جاب ویژن'), ('jobinja', 'جابینجا'), ('e-estekhdam', 'آی‌استخدام'), ('divar', 'دیوار'), ('karino', 'کارینو')]
    STARTS = {'jobvision': 1000, 'jobinja': 2000, 'e-estekhdam': 3000, 'divar': 4000, 'karino': 5000}
    platform = models.CharField('پلتفرم', max_length=20, choices=PLATFORMS)
    number = models.PositiveIntegerField('شناسه آگهی', editable=False)
    role_key = models.CharField('سمت', max_length=200)
    role_title = models.CharField('عنوان سمت هنگام ثبت', max_length=200)
    email = models.EmailField('ایمیل', blank=True)
    is_active = models.BooleanField('فعال', default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [models.UniqueConstraint(fields=['platform', 'number'], name='unique_hiring_ad_platform_number')]

    def __str__(self):
        return f'{self.role_title} — {self.get_platform_display()} · {self.number}'


class HiringApplication(models.Model):
    STATUSES = [('arrived', 'مراجعه کرده'), ('interviewed', 'مصاحبه شده'), ('repeat', 'مصاحبه مجدد'), ('rejected', 'رد کارجو'), ('invited', 'دعوت به همکاری')]
    reception = models.OneToOneField('customers.Reception', on_delete=models.CASCADE, related_name='hiring')
    job_ad = models.ForeignKey(HiringAd, null=True, blank=True, on_delete=models.PROTECT, related_name='applications')
    resume = models.FileField('رزومه', storage=HiringDocumentStorage(), upload_to=resume_path, max_length=255, blank=True)
    resume_name = models.CharField(max_length=200, blank=True)
    resume_uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    status = models.CharField('وضعیت استخدام', choices=STATUSES, max_length=20, default='arrived', db_index=True)
    latest_session = models.ForeignKey('customers.InterviewSession', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)
    current_arrived_at = models.DateTimeField('آخرین ورود', null=True, blank=True)


class InterviewSession(models.Model):
    BEHAVIORS = [('friendly', 'اجتماعی و دوستانه'), ('formal', 'رسمی و محافظه‌کار'), ('determined', 'مصمم و جسور'), ('hesitant', 'محتاط و مردد'), ('toxic', 'رفتار سمی'), ('other', 'سایر')]
    FIT = [('fully', 'کاملاً'), ('high', 'زیاد'), ('medium', 'متوسط'), ('low', 'کم'), ('unknown', 'نامعلوم')]
    LEVELS = [('low', 'کم'), ('medium', 'متوسط'), ('high', 'زیاد')]
    QUESTIONS = [('technical', 'سوالات تخصصی پرسید'), ('irrelevant', 'سوالات حاشیه‌ای پرسید'), ('conditions', 'از شرایط کاری پرسید'), ('none', 'هیچ سوالی نپرسید')]
    RESULTS = [('rejected', 'رد'), ('accepted', 'قبول'), ('repeat', 'مصاحبه مجدد')]
    REASONS = [('skills', 'عدم تطابق تخصص با سمت درخواستی'), ('experience', 'عدم تجربه کافی'), ('salary', 'حقوق درخواستی بالا'), ('culture', 'عدم هماهنگی رفتاری با فرهنگ سازمان'), ('availability', 'عدم امکان شروع فوری'), ('performance', 'عملکرد ضعیف در مصاحبه تخصصی'), ('absent', 'غیبت در جلسه مصاحبه'), ('other', 'سایر')]
    EXPERIENCE = [('related', 'دارای تجربه مرتبط'), ('limited', 'تجربه محدود'), ('training', 'بدون تجربه و نیازمند آموزش')]
    COLLABORATION = [('pending_docs', 'بله (عدم تکمیل مدارک)'), ('rejected_day_one', 'خیر (عدم برخورد صحیح در روز اول یا مشاهده حاشیه و سوالات سمی بعد ورود)')]
    application = models.ForeignKey(HiringApplication, on_delete=models.CASCADE, related_name='sessions')
    round_number = models.PositiveIntegerField()
    kind = models.CharField(max_length=10, choices=[('first', 'شروع مصاحبه'), ('repeat', 'مصاحبه مجدد')])
    started_at = models.DateTimeField(default=timezone.now, editable=False)
    arrived_at = models.DateTimeField('ورود این جلسه', null=True, blank=True, editable=False)
    ended_at = models.DateTimeField(null=True, blank=True, editable=False)
    saved_at = models.DateTimeField(null=True, blank=True, editable=False)
    interviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    saved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    job_ad = models.ForeignKey(HiringAd, null=True, blank=True, on_delete=models.PROTECT, related_name='interviews')
    waiting_seconds = models.PositiveIntegerField(null=True, blank=True, editable=False)
    behavior = models.CharField('نوع برخورد', max_length=20, choices=BEHAVIORS, blank=True)
    fit = models.CharField('میزان انطباق با سمت درخواستی', max_length=20, choices=FIT, blank=True)
    seriousness = models.CharField('میزان جدی بودن درخواست کار', max_length=20, choices=LEVELS, blank=True)
    questions = models.CharField('سوالات کارجو', max_length=20, choices=QUESTIONS, blank=True)
    notes = models.TextField('توضیحات', blank=True)
    grade = models.CharField('امتیازدهی', max_length=1, choices=[(x, x) for x in 'ABCDE'], blank=True)
    result = models.CharField('نتیجه مصاحبه', max_length=20, choices=RESULTS, blank=True)
    rejection_reason = models.CharField('دلیل رد شدن', max_length=20, choices=REASONS, blank=True)
    proposed_role = models.CharField('سمت پیشنهادی', max_length=200, blank=True)
    proposed_role_title = models.CharField(max_length=200, blank=True)
    experience = models.CharField('تجربه کاری مرتبط', max_length=20, choices=EXPERIENCE, blank=True)
    next_interview_at = models.DateTimeField('مصاحبه بعدی', null=True, blank=True)
    invite = models.BooleanField('دعوت به همکاری', default=False)
    will_attend = models.CharField('حضور پیدا می‌کند؟', choices=[('yes', 'بله'), ('no', 'خیر')], max_length=3, blank=True)
    invitation_at = models.DateTimeField('تاریخ و ساعت دعوت', null=True, blank=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    collaboration = models.CharField('تبدیل به همکار', choices=COLLABORATION, max_length=20, blank=True)

    class Meta:
        ordering = ['-round_number']
        constraints = [models.UniqueConstraint(fields=['application', 'round_number'], name='unique_application_interview_round'), models.UniqueConstraint(fields=['application'], condition=models.Q(saved_at__isnull=True), name='one_unsaved_interview_per_application')]

    @property
    def seconds(self):
        return max(0, int(((self.ended_at or timezone.now()) - self.started_at).total_seconds()))

    @property
    def minutes(self):
        return round(self.seconds / 60, 1)

    @property
    def waiting_minutes(self):
        return round(self.waiting_seconds / 60, 1) if self.waiting_seconds is not None else None


class HiringReferral(models.Model):
    application = models.ForeignKey(HiringApplication, on_delete=models.CASCADE, related_name='referrals')
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)
