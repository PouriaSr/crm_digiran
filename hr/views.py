import jdatetime
from datetime import timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from accounts.permissions import require_permission, has_permission
from .models import Employee, Task, LeaveRequest, Attendance
from .forms import EmployeeForm, TaskForm, LeaveRequestForm, AttendanceForm, MyProfileForm
from crm.duplicate_check import show_duplicate_warnings


# ═══════════════════════════════════════════
# پرسنل
# ═══════════════════════════════════════════

@login_required
@require_permission('hr.view_employees')
def employee_list(request):
    employees = Employee.objects.all()

    search = request.GET.get('q', '').strip()
    if search:
        employees = employees.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(mobile__icontains=search) |
            Q(national_id__icontains=search)
        )

    position = request.GET.get('position', '')
    if position:
        employees = employees.filter(position=position)

    status = request.GET.get('status', '')
    if status == 'active':
        employees = employees.filter(is_active=True)
    elif status == 'inactive':
        employees = employees.filter(is_active=False)

    stats = {
        'total': Employee.objects.count(),
        'active': Employee.objects.filter(is_active=True).count(),
        'inactive': Employee.objects.filter(is_active=False).count(),
    }

    paginator = Paginator(employees, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'page_obj': page_obj,
        'stats': stats,
        'search': search,
        'current_position': position,
        'current_status': status,
        'position_choices': Employee.POSITION_CHOICES,
    }
    return render(request, 'hr/employee_list.html', context)


@login_required
@require_permission('hr.view_employees')
def employee_detail(request, pk):
    employee = get_object_or_404(Employee, pk=pk)

    open_tasks = employee.tasks.filter(
        status__in=['pending', 'in_progress']
    ).order_by('due_date')[:10]

    done_tasks_count = employee.tasks.filter(status='done').count()
    open_tasks_count = employee.tasks.filter(
        status__in=['pending', 'in_progress']
    ).count()

    context = {
        'employee': employee,
        'open_tasks': open_tasks,
        'done_tasks_count': done_tasks_count,
        'open_tasks_count': open_tasks_count,
    }
    return render(request, 'hr/employee_detail.html', context)


@login_required
@require_permission('hr.manage_employees')
def employee_create(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save()
            show_duplicate_warnings(request, form)

            # ⭐ Fix #19: هشدار کیفیت داده اگر کد ملی خالی است
            # (کارمندانی که nid ندارند، در آینده ممکن است دو رکورد ناخواسته ایجاد کنند)
            if not employee.national_id:
                empty_nid_count = Employee.objects.filter(
                    Q(national_id__isnull=True) | Q(national_id='')
                ).exclude(pk=employee.pk).count()
                if empty_nid_count > 0:
                    messages.warning(
                        request,
                        f'توجه: {empty_nid_count} کارمند دیگر هم بدون کد ملی ثبت شده‌اند. '
                        'برای کیفیت داده بهتر است کد ملی این کارمند را تکمیل کنید.'
                    )

            messages.success(request, f'کارمند «{employee.full_name}» اضافه شد.')
            return redirect('hr:employee_detail', pk=employee.pk)
    else:
        form = EmployeeForm()

    return render(request, 'hr/employee_form.html', {
        'form': form,
        'title': 'افزودن کارمند جدید',
        'submit_label': 'ذخیره',
    })


@login_required
@require_permission('hr.manage_employees')
def employee_edit(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            show_duplicate_warnings(request, form)
            messages.success(request, 'اطلاعات کارمند به‌روزرسانی شد.')
            return redirect('hr:employee_detail', pk=employee.pk)
    else:
        form = EmployeeForm(instance=employee)

    return render(request, 'hr/employee_form.html', {
        'form': form,
        'title': f'ویرایش {employee.full_name}',
        'submit_label': 'ذخیره تغییرات',
        'employee': employee,
    })


@login_required
@require_permission('hr.manage_employees')
def employee_delete(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        name = employee.full_name
        employee.delete()
        messages.success(request, f'کارمند «{name}» حذف شد.')
        return redirect('hr:employee_list')
    return render(request, 'hr/employee_confirm_delete.html', {'employee': employee})


# ═══════════════════════════════════════════
# وظایف
# ═══════════════════════════════════════════

@login_required
@require_permission('hr.view_tasks')
def task_list(request):
    # ⭐ متغیر today به بالای تابع منتقل شد تا در فیلترها قابل استفاده باشد
    today = timezone.now().date()

    tasks = Task.objects.select_related('assigned_to', 'created_by').all()

    search = request.GET.get('q', '').strip()
    if search:
        tasks = tasks.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search)
        )

    status = request.GET.get('status', '')
    if status:
        tasks = tasks.filter(status=status)

    priority = request.GET.get('priority', '')
    if priority:
        tasks = tasks.filter(priority=priority)

    employee = request.GET.get('employee', '')
    if employee:
        tasks = tasks.filter(assigned_to_id=employee)

    # ⭐ فیلتر جدید برای اعلان‌ها
    due = request.GET.get('due', '')
    if due == 'overdue':
        tasks = tasks.filter(due_date__lt=today).exclude(status__in=['done', 'cancelled'])

    stats = {
        'total': Task.objects.count(),
        'pending': Task.objects.filter(status='pending').count(),
        'in_progress': Task.objects.filter(status='in_progress').count(),
        'overdue': Task.objects.filter(
            due_date__lt=today
        ).exclude(status__in=['done', 'cancelled']).count(),
    }

    paginator = Paginator(tasks, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    employees = Employee.objects.filter(is_active=True)

    context = {
        'page_obj': page_obj,
        'stats': stats,
        'search': search,
        'current_status': status,
        'current_priority': priority,
        'current_employee': employee,
        'employees': employees,
        'status_choices': Task.STATUS_CHOICES,
        'priority_choices': Task.PRIORITY_CHOICES,
    }
    return render(request, 'hr/task_list.html', context)


@login_required
@require_permission('hr.view_tasks')
def task_detail(request, pk):
    task = get_object_or_404(Task, pk=pk)
    return render(request, 'hr/task_detail.html', {'task': task})


@login_required
@require_permission('hr.manage_tasks')
def task_create(request):
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            task.save()
            messages.success(request, f'وظیفه «{task.title}» ثبت شد.')
            return redirect('hr:task_detail', pk=task.pk)
    else:
        form = TaskForm()

    return render(request, 'hr/task_form.html', {
        'form': form,
        'title': 'افزودن وظیفه جدید',
        'submit_label': 'ذخیره',
    })


@login_required
@require_permission('hr.manage_tasks')
def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, 'وظیفه به‌روزرسانی شد.')
            return redirect('hr:task_detail', pk=task.pk)
    else:
        form = TaskForm(instance=task)

    return render(request, 'hr/task_form.html', {
        'form': form,
        'title': f'ویرایش: {task.title}',
        'submit_label': 'ذخیره تغییرات',
        'task': task,
    })


@login_required
@require_permission('hr.manage_tasks')
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if request.method == 'POST':
        title = task.title
        task.delete()
        messages.success(request, f'وظیفه «{title}» حذف شد.')
        return redirect('hr:task_list')
    return render(request, 'hr/task_confirm_delete.html', {'task': task})


@login_required
@require_permission('hr.manage_tasks')
def task_toggle_status(request, pk):
    """
    ⭐ Fix #18: برای status نامعتبر هم بازخورد می‌دهد (قبلاً سکوت می‌کرد).
    """
    task = get_object_or_404(Task, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status', '').strip()
        valid_statuses = dict(Task.STATUS_CHOICES)

        if new_status in valid_statuses:
            task.status = new_status
            task.save()
            messages.success(
                request,
                f'وضعیت وظیفه به «{task.get_status_display()}» تغییر کرد.'
            )
        else:
            messages.error(
                request,
                f'وضعیت «{new_status or "(خالی)"}» نامعتبر است. '
                'لطفاً یکی از گزینه‌های موجود را انتخاب کنید.'
            )
    else:
        # درخواست GET → پیام مناسب
        messages.warning(request, 'تغییر وضعیت فقط با POST امکان‌پذیر است.')

    return redirect('hr:task_detail', pk=task.pk)


# ═══════════════════════════════════════════
# مرخصی‌ها
# ═══════════════════════════════════════════

@login_required
def leave_list(request):
    can_review = has_permission(request.user, 'hr.review_leaves')

    leaves = LeaveRequest.objects.select_related('employee', 'reviewed_by').all()

    if not can_review:
        if hasattr(request.user, 'employee_profile'):
            leaves = leaves.filter(employee=request.user.employee_profile)
        else:
            leaves = leaves.none()

    status = request.GET.get('status', '')
    if status:
        leaves = leaves.filter(status=status)

    leave_type = request.GET.get('leave_type', '')
    if leave_type:
        leaves = leaves.filter(leave_type=leave_type)

    search = request.GET.get('q', '').strip()
    if search:
        leaves = leaves.filter(
            Q(employee__first_name__icontains=search) |
            Q(employee__last_name__icontains=search) |
            Q(reason__icontains=search)
        )

    stats_qs = LeaveRequest.objects.all()
    if not can_review:
        if hasattr(request.user, 'employee_profile'):
            stats_qs = stats_qs.filter(employee=request.user.employee_profile)
        else:
            stats_qs = stats_qs.none()

    stats = {
        'total': stats_qs.count(),
        'pending': stats_qs.filter(status='pending').count(),
        'approved': stats_qs.filter(status='approved').count(),
        'rejected': stats_qs.filter(status='rejected').count(),
    }

    paginator = Paginator(leaves, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'page_obj': page_obj,
        'stats': stats,
        'search': search,
        'current_status': status,
        'current_type': leave_type,
        'status_choices': LeaveRequest.STATUS_CHOICES,
        'type_choices': LeaveRequest.LEAVE_TYPE_CHOICES,
    }
    return render(request, 'hr/leave_list.html', context)


@login_required
def leave_create(request):
    can_review = has_permission(request.user, 'hr.review_leaves')
    has_profile = hasattr(request.user, 'employee_profile')

    if not (can_review or has_profile):
        messages.error(request, 'شما پروفایل پرسنلی ندارید و نمی‌توانید درخواست مرخصی ثبت کنید.')
        return redirect('dashboard:home')

    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, user=request.user)
        if form.is_valid():
            leave = form.save()
            messages.success(request, 'درخواست مرخصی ثبت شد.')
            return redirect('hr:leave_list')
    else:
        form = LeaveRequestForm(user=request.user)

    return render(request, 'hr/leave_form.html', {
        'form': form,
        'title': 'ثبت درخواست مرخصی',
        'submit_label': 'ثبت درخواست',
    })


@login_required
@require_permission('hr.review_leaves')
def leave_review(request, pk):
    """
    ⭐ Fix #10: action نامعتبر → خطا و redirect قبل از ذخیره‌ی reviewer.
    قبلاً اگر action نامعتبر بود، status تغییر نمی‌کرد ولی reviewed_by/reviewed_at
    ست می‌شد → رکورد «بررسی‌شده‌ی ناتمام» ثبت می‌شد.
    """
    leave = get_object_or_404(LeaveRequest, pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action', '').strip()
        note = request.POST.get('review_note', '').strip()

        if action not in ('approve', 'reject'):
            messages.error(
                request,
                'عملیات نامعتبر است. لطفاً یکی از گزینه‌های «تایید» یا «رد» را انتخاب کنید.'
            )
            return redirect('hr:leave_review', pk=pk)

        if action == 'approve':
            leave.status = 'approved'
        else:  # action == 'reject'
            leave.status = 'rejected'

        leave.reviewed_by = request.user
        leave.reviewed_at = timezone.now()
        leave.review_note = note
        leave.save()

        messages.success(request, f'درخواست {leave.get_status_display()}.')
        return redirect('hr:leave_list')

    return render(request, 'hr/leave_review.html', {'leave': leave})


# ═══════════════════════════════════════════
# حضور و غیاب
# ═══════════════════════════════════════════

@login_required
@require_permission('hr.attendance')
def attendance_list(request):
    attendances = Attendance.objects.select_related('employee').all()

    from_date = request.GET.get('from', '')
    to_date = request.GET.get('to', '')

    if from_date:
        try:
            j = jdatetime.date(*map(int, from_date.split('/')))
            g = j.togregorian()
            attendances = attendances.filter(date__gte=g)
        except (ValueError, AttributeError):
            pass
    else:
        attendances = attendances.filter(date=timezone.now().date())

    if to_date:
        try:
            j = jdatetime.date(*map(int, to_date.split('/')))
            g = j.togregorian()
            attendances = attendances.filter(date__lte=g)
        except (ValueError, AttributeError):
            pass

    employee = request.GET.get('employee', '')
    if employee:
        attendances = attendances.filter(employee_id=employee)

    status = request.GET.get('status', '')
    if status:
        attendances = attendances.filter(status=status)

    stats = {
        'today': Attendance.objects.filter(date=timezone.now().date()).count(),
        'present_today': Attendance.objects.filter(
            date=timezone.now().date(), status='present'
        ).count(),
        'late_today': Attendance.objects.filter(
            date=timezone.now().date(), status='late'
        ).count(),
        'absent_today': Attendance.objects.filter(
            date=timezone.now().date(), status='absent'
        ).count(),
    }

    paginator = Paginator(attendances, 30)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    employees = Employee.objects.filter(is_active=True)

    context = {
        'page_obj': page_obj,
        'stats': stats,
        'from_date': from_date,
        'to_date': to_date,
        'current_employee': employee,
        'current_status': status,
        'employees': employees,
        'status_choices': Attendance.STATUS_CHOICES,
    }
    return render(request, 'hr/attendance_list.html', context)


@login_required
@require_permission('hr.attendance')
def attendance_create(request):
    if request.method == 'POST':
        form = AttendanceForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'رکورد حضور و غیاب ثبت شد.')
                return redirect('hr:attendance_list')
            except Exception:
                messages.error(request, 'برای این کارمند در این روز قبلاً رکوردی ثبت شده.')
    else:
        form = AttendanceForm()

    return render(request, 'hr/attendance_form.html', {
        'form': form,
        'title': 'ثبت حضور و غیاب',
        'submit_label': 'ثبت',
    })


@login_required
@require_permission('hr.attendance')
def attendance_edit(request, pk):
    attendance = get_object_or_404(Attendance, pk=pk)
    if request.method == 'POST':
        form = AttendanceForm(request.POST, instance=attendance)
        if form.is_valid():
            form.save()
            messages.success(request, 'رکورد به‌روزرسانی شد.')
            return redirect('hr:attendance_list')
    else:
        form = AttendanceForm(instance=attendance)

    return render(request, 'hr/attendance_form.html', {
        'form': form,
        'title': f'ویرایش حضور {attendance.employee.full_name}',
        'submit_label': 'ذخیره',
        'attendance': attendance,
    })


@login_required
@require_permission('hr.attendance')
def attendance_delete(request, pk):
    attendance = get_object_or_404(Attendance, pk=pk)
    if request.method == 'POST':
        attendance.delete()
        messages.success(request, 'رکورد حذف شد.')
        return redirect('hr:attendance_list')
    return render(request, 'hr/attendance_confirm_delete.html', {'attendance': attendance})


@login_required
@require_permission('hr.attendance')
def attendance_report(request):
    import jdatetime
    from datetime import timedelta
    from django.db.models import Count, Q, Sum
    from django.utils import timezone

    now = timezone.now()
    j_now = jdatetime.date.fromgregorian(date=now.date())

    try:
        selected_year = int(request.GET.get('year', j_now.year))
    except (ValueError, TypeError):
        selected_year = j_now.year

    try:
        selected_month_num = int(request.GET.get('month_num', j_now.month))
    except (ValueError, TypeError):
        selected_month_num = j_now.month

    if not (1 <= selected_month_num <= 12):
        selected_month_num = j_now.month

    month_start = jdatetime.date(selected_year, selected_month_num, 1).togregorian()
    if selected_month_num == 12:
        next_month = jdatetime.date(selected_year + 1, 1, 1)
    else:
        next_month = jdatetime.date(selected_year, selected_month_num + 1, 1)
    month_end = next_month.togregorian() - timedelta(days=1)

    year_choices = list(range(j_now.year - 3, j_now.year + 2))
    month_choices = [
        (1, 'فروردین'), (2, 'اردیبهشت'), (3, 'خرداد'), (4, 'تیر'),
        (5, 'مرداد'), (6, 'شهریور'), (7, 'مهر'), (8, 'آبان'),
        (9, 'آذر'), (10, 'دی'), (11, 'بهمن'), (12, 'اسفند'),
    ]

    employees = list(Employee.objects.filter(is_active=True))
    employee_ids = [e.pk for e in employees]

    base_qs = Attendance.objects.filter(
        date__gte=month_start,
        date__lte=month_end,
        employee_id__in=employee_ids,
    )

    counts_qs = base_qs.values('employee_id').annotate(
        total_days=Count('id'),
        present=Count('id', filter=Q(status='present')),
        late=Count('id', filter=Q(status='late')),
        absent=Count('id', filter=Q(status='absent')),
        leave=Count('id', filter=Q(status='leave')),
    )
    counts_map = {row['employee_id']: row for row in counts_qs}

    hours_map = {}
    for rec in base_qs.only('employee_id', 'check_in', 'check_out'):
        wh = rec.work_hours
        if wh:
            hours_map[rec.employee_id] = hours_map.get(rec.employee_id, 0) + wh

    report = []
    for emp in employees:
        c = counts_map.get(emp.pk, {})
        report.append({
            'employee': emp,
            'total_days': c.get('total_days', 0),
            'present': c.get('present', 0),
            'late': c.get('late', 0),
            'absent': c.get('absent', 0),
            'leave': c.get('leave', 0),
            'total_hours': round(hours_map.get(emp.pk, 0), 1),
        })

    context = {
        'report': report,
        'month_start': month_start,
        'month_end': month_end,
        'selected_year': selected_year,
        'selected_month_num': selected_month_num,
        'year_choices': year_choices,
        'month_choices': month_choices,
    }
    return render(request, 'hr/attendance_report.html', context)


# ═══════════════════════════════════════════
# پروفایل من
# ═══════════════════════════════════════════

@login_required
def my_profile(request):
    from django_otp.plugins.otp_totp.models import TOTPDevice
    from django_otp.plugins.otp_static.models import StaticDevice

    try:
        employee = request.user.employee_profile
    except Employee.DoesNotExist:
        messages.warning(request, 'برای حساب کاربری شما پروفایل پرسنلی ثبت نشده است.')
        return redirect('dashboard:home')

    calls_count = request.user.calls.count()
    invoices_count = request.user.created_invoices.count()
    created_customers_count = request.user.created_customers.count()

    open_tasks = employee.tasks.filter(
        status__in=['pending', 'in_progress']
    ).order_by('due_date')

    done_tasks = employee.tasks.filter(
        status='done'
    ).order_by('-completed_at')[:5]

    totp_device = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
    has_2fa = totp_device is not None

    recovery_codes_count = 0
    if has_2fa:
        static_device = StaticDevice.objects.filter(user=request.user).first()
        if static_device:
            recovery_codes_count = static_device.token_set.count()

    context = {
        'employee': employee,
        'open_tasks': open_tasks,
        'done_tasks': done_tasks,
        'calls_count': calls_count,
        'invoices_count': invoices_count,
        'created_customers_count': created_customers_count,
        'has_2fa': has_2fa,
        'recovery_codes_count': recovery_codes_count,
    }
    return render(request, 'hr/my_profile.html', context)


@login_required
def edit_my_profile(request):
    try:
        employee = request.user.employee_profile
    except Employee.DoesNotExist:
        messages.warning(request, 'برای حساب کاربری شما پروفایل پرسنلی ثبت نشده است.')
        return redirect('dashboard:home')

    if request.method == 'POST':
        form = MyProfileForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, 'اطلاعات پروفایل شما با موفقیت به‌روزرسانی شد.')
            return redirect('hr:my_profile')
    else:
        form = MyProfileForm(instance=employee)

    return render(request, 'hr/profile_edit.html', {
        'form': form,
    })