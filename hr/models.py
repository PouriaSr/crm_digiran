from datetime import datetime
from django.db import models, transaction
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.utils import timezone


class Employee(models.Model):
    """مدل پرسنل — اطلاعات کارمندان"""

    POSITION_CHOICES = [
        ('manager', 'مدیر'),
        ('sales', 'کارشناس فروش'),
        ('support', 'پشتیبان'),
        ('technician', 'تکنسین'),
        ('accountant', 'حسابدار'),
        ('operator', 'اپراتور'),
        ('other', 'سایر'),
    ]

    CONTRACT_CHOICES = [
        ('full_time', 'تمام وقت'),
        ('part_time', 'پاره وقت'),
        ('contractor', 'پیمانکار'),
        ('intern', 'کارآموز'),
    ]

    user = models.OneToOneField(
    User, on_delete=models.SET_NULL,
    related_name='employee_profile',
    verbose_name='کاربر',
    null=True, blank=True,
    help_text='اگر کاربر حذف شود، پروفایل پرسنلی باقی می‌ماند'
)

    first_name = models.CharField('نام', max_length=100)
    last_name = models.CharField('نام خانوادگی', max_length=100)
    national_id = models.CharField('کد ملی', max_length=10, blank=True, null=True, db_index=True)
    mobile = models.CharField('شماره تماس', max_length=15, blank=True, null=True, db_index=True)
    email = models.EmailField('ایمیل', blank=True, null=True)
    address = models.TextField('آدرس', blank=True, null=True)
    birth_date = models.DateField('تاریخ تولد', null=True, blank=True)

    position = models.CharField('سمت', max_length=20,
                                 choices=POSITION_CHOICES, default='other')
    contract_type = models.CharField('نوع قرارداد', max_length=20,
                                      choices=CONTRACT_CHOICES, default='full_time')
    hire_date = models.DateTimeField('تاریخ استخدام', default=timezone.now)
    salary = models.DecimalField('حقوق پایه (تومان)', max_digits=15, decimal_places=0,
                                  default=0, blank=True, null=True)
    is_active = models.BooleanField('فعال', default=True)

    notes = models.TextField('یادداشت', blank=True, null=True)

    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)
    updated_at = models.DateTimeField('آخرین ویرایش', auto_now=True)

    class Meta:
        verbose_name = 'کارمند'
        verbose_name_plural = 'پرسنل'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def open_tasks_count(self):
        return self.tasks.filter(status__in=['pending', 'in_progress', 'follow_up']).count()


class Task(models.Model):
    """مدل وظیفه — تسک‌های کاری"""

    PRIORITY_CHOICES = [
        ('low', 'کم'),
        ('medium', 'متوسط'),
        ('high', 'زیاد'),
        ('urgent', 'فوری'),
    ]

    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('in_progress', 'در حال انجام'),
        ('follow_up', 'در پیگیری'),
        ('done', 'انجام شده'),
        ('cancelled', 'لغو شده'),
    ]

    title = models.CharField('عنوان وظیفه', max_length=200)
    description = models.TextField('توضیحات', blank=True, null=True)

    assigned_to = models.ForeignKey(
        Employee, on_delete=models.CASCADE, null=True, blank=True,
        related_name='tasks', verbose_name='مسئول'
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_tasks', verbose_name='ایجادکننده'
    )

    priority = models.CharField('اولویت', max_length=10,
                                 choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField('وضعیت', max_length=20,
                               choices=STATUS_CHOICES, default='pending', db_index=True)

    due_date = models.DateField('مهلت انجام', null=True, blank=True, db_index=True)
    due_time = models.TimeField('ساعت انجام', null=True, blank=True)
    assigned_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='direct_tasks', verbose_name='کاربر مسئول')
    hiring_session = models.OneToOneField('customers.InterviewSession', null=True, blank=True, on_delete=models.CASCADE, related_name='next_task', verbose_name='جلسه تعیین‌کننده موعد')
    performed_session = models.OneToOneField('customers.InterviewSession', null=True, blank=True, on_delete=models.SET_NULL, related_name='scheduled_task', verbose_name='جلسه انجام‌شده')

    source_key = models.CharField(max_length=120, null=True, blank=True, unique=True, editable=False)
    source_type = models.CharField(max_length=24, blank=True, editable=False)
    source_id = models.PositiveBigIntegerField(null=True, blank=True, editable=False)
    source_customer = models.ForeignKey('customers.Customer', null=True, blank=True, on_delete=models.SET_NULL, related_name='workflow_tasks', editable=False)

    queued_at = models.DateTimeField('آخرین تخصیص یا فعال‌سازی', null=True, blank=True, editable=False)
    completed_at = models.DateTimeField('تاریخ اتمام', null=True, blank=True)

    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)
    updated_at = models.DateTimeField('آخرین ویرایش', auto_now=True)

    class Meta:
        verbose_name = 'وظیفه'
        verbose_name_plural = 'وظایف'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def needs_assignment(self):
        return bool((self.source_type or self.hiring_session_id) and self.status not in ('done','cancelled') and
                    not self.assigned_user_id and (not self.assigned_to_id or not self.assigned_to.user_id))

    @property
    def workflow_status_display(self):
        if self.needs_assignment:return 'نیازمند تعیین مسئول'
        if self.status=='pending':
            if self.hiring_session_id:return 'در انتظار مصاحبه مجدد'
            return {'admission':'در انتظار ثبت ورود','reception':'در انتظار ارجاع','registration':'در انتظار ثبت اطلاعات','case':'در انتظار تکمیل پرونده','interview':'در انتظار مصاحبه'}.get(self.source_type,self.get_status_display())
        if self.status=='in_progress' and self.source_type=='case':return 'در حال تکمیل پرونده'
        return self.get_status_display()

    @property
    def responsible_display(self):
        if self.assigned_user_id:
            return self.assigned_user.get_full_name() or self.assigned_user.username
        return self.assigned_to.full_name if self.assigned_to_id else 'نیازمند تعیین مسئول' if self.needs_assignment else 'تعیین نشده'

    @property
    def recruitment_url(self):
        from django.urls import reverse
        return reverse('customers:hiring_task', args=[self.hiring_session.application.reception_id])

    @property
    def is_overdue(self):
        if self.due_date and self.due_time and self.status not in ('done', 'cancelled'):
            return timezone.make_aware(datetime.combine(self.due_date, self.due_time)) < timezone.now()
        if self.due_date and self.status not in ('done', 'cancelled'):
            return self.due_date < timezone.localdate()
        return False

    @property
    def priority_color(self):
        return {
            'low': 'gray',
            'medium': 'blue',
            'high': 'orange',
            'urgent': 'red',
        }.get(self.priority, 'gray')

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.pk:
                previous = Task.objects.select_for_update().filter(pk=self.pk).values('status', 'assigned_user_id', 'assigned_to_id').first()
                if previous and self.status not in ('done', 'cancelled') and (previous['status'] in ('done', 'cancelled') or previous['assigned_user_id'] != self.assigned_user_id or previous['assigned_to_id'] != self.assigned_to_id):
                    self.queued_at = timezone.now()
                    if kwargs.get('update_fields'):
                        kwargs['update_fields'] = set(kwargs['update_fields']) | {'queued_at'}
            if self.status == 'done' and not self.completed_at:
                self.completed_at = timezone.now()
            elif self.status != 'done':
                self.completed_at = None
            if kwargs.get('update_fields') and 'status' in kwargs['update_fields']:
                kwargs['update_fields'] = set(kwargs['update_fields']) | {'completed_at'}
            super().save(*args, **kwargs)


class LeaveRequest(models.Model):
    """مدل درخواست مرخصی"""

    LEAVE_TYPE_CHOICES = [
        ('annual', 'استحقاقی'),
        ('sick', 'استعلاجی'),
        ('unpaid', 'بدون حقوق'),
        ('maternity', 'زایمان'),
        ('marriage', 'ازدواج'),
        ('other', 'سایر'),
    ]

    STATUS_CHOICES = [
        ('pending', 'در انتظار تأیید'),
        ('approved', 'تأیید شده'),
        ('rejected', 'رد شده'),
        ('cancelled', 'لغو شده'),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='leave_requests', verbose_name='کارمند'
    )
    leave_type = models.CharField('نوع مرخصی', max_length=20,
                                   choices=LEAVE_TYPE_CHOICES, default='annual')

    start_date = models.DateField('از تاریخ', db_index=True)
    end_date = models.DateField('تا تاریخ', db_index=True)
    days_count = models.PositiveIntegerField('تعداد روز', default=1)

    reason = models.TextField('علت', blank=True, null=True)

    status = models.CharField('وضعیت', max_length=20,
                               choices=STATUS_CHOICES, default='pending', db_index=True)

    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_leaves', verbose_name='بررسی‌کننده'
    )
    reviewed_at = models.DateTimeField('تاریخ بررسی', null=True, blank=True)
    review_note = models.TextField('یادداشت بررسی', blank=True, null=True)

    created_at = models.DateTimeField('تاریخ ثبت', auto_now_add=True)
    updated_at = models.DateTimeField('آخرین ویرایش', auto_now=True)

    class Meta:
        verbose_name = 'درخواست مرخصی'
        verbose_name_plural = 'درخواست‌های مرخصی'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee.full_name} - {self.get_leave_type_display()}"

    def save(self, *args, **kwargs):
        if self.start_date and self.end_date:
            self.days_count = (self.end_date - self.start_date).days + 1
        super().save(*args, **kwargs)

    @property
    def is_pending(self):
        return self.status == 'pending'


class Attendance(models.Model):
    """مدل حضور و غیاب روزانه"""

    STATUS_CHOICES = [
        ('present', 'حاضر'),
        ('absent', 'غایب'),
        ('late', 'تاخیر'),
        ('leave', 'مرخصی'),
        ('holiday', 'تعطیل'),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='attendances', verbose_name='کارمند'
    )
    date = models.DateField('تاریخ', default=timezone.now)

    check_in = models.TimeField('ساعت ورود', null=True, blank=True)
    check_out = models.TimeField('ساعت خروج', null=True, blank=True)

    status = models.CharField('وضعیت', max_length=20,
                               choices=STATUS_CHOICES, default='present', db_index=True)

    notes = models.TextField('یادداشت', blank=True, null=True)

    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)
    updated_at = models.DateTimeField('آخرین ویرایش', auto_now=True)

    class Meta:
        verbose_name = 'حضور و غیاب'
        verbose_name_plural = 'حضور و غیاب'
        ordering = ['-date']
        unique_together = ['employee', 'date']

    def __str__(self):
        return f"{self.employee.full_name} - {self.date}"

    @property
    def work_hours(self):
        if not self.check_in or not self.check_out:
            return None

        from datetime import datetime, timedelta
        today = datetime.today().date()
        check_in_dt = datetime.combine(today, self.check_in)
        check_out_dt = datetime.combine(today, self.check_out)

        if check_out_dt < check_in_dt:
            check_out_dt += timedelta(days=1)

        diff = check_out_dt - check_in_dt
        return round(diff.total_seconds() / 3600, 2)

    @property
    def work_hours_display(self):
        hours = self.work_hours
        if hours is None:
            return '—'
        h = int(hours)
        m = int((hours - h) * 60)
        if m == 0:
            return f'{h} ساعت'
        return f'{h} ساعت و {m} دقیقه'

class TaskEvent(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='events')
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    report_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='task_report_requests')
    report_required = models.BooleanField(default=False)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def get_transition_display(self):
        choices = dict(Task.STATUS_CHOICES)
        return choices.get(self.from_status, self.from_status) + ' ← ' + choices.get(self.to_status, self.to_status)

    class Meta:
        ordering = ['-pk']


class TaskReport(models.Model):
    event = models.OneToOneField(TaskEvent, on_delete=models.CASCADE, related_name='report')
    author = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    text = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)


class TaskNotice(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='notices')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_notices')
    text = models.CharField(max_length=250)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-pk']
        indexes = [models.Index(fields=['user', 'read_at'])]
