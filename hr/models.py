from django.db import models
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
        return self.tasks.filter(status__in=['pending', 'in_progress']).count()


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
        ('done', 'انجام شده'),
        ('cancelled', 'لغو شده'),
    ]

    title = models.CharField('عنوان وظیفه', max_length=200)
    description = models.TextField('توضیحات', blank=True, null=True)

    assigned_to = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
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
    def is_overdue(self):
        if self.due_date and self.status not in ('done', 'cancelled'):
            return self.due_date < timezone.now().date()
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
        if self.status == 'done' and not self.completed_at:
            self.completed_at = timezone.now()
        elif self.status != 'done':
            self.completed_at = None

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
        ('pending', 'در انتظار تایید'),
        ('approved', 'تایید شده'),
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