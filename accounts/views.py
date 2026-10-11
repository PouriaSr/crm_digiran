from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from accounts.permissions import require_permission
from .forms import UserCreateForm, UserEditForm, UserPasswordForm, get_user_role, ensure_groups


# ═══════════════════════════════════════════════════════════
# مدیریت کاربران — همه با require_permission (۸.۱)
# ═══════════════════════════════════════════════════════════

@login_required
@require_permission('accounts.manage_users')
def user_list(request):
    # اطمینان از وجود گروه‌ها
    ensure_groups()

    users = User.objects.all().prefetch_related('groups').order_by('-date_joined')

    # جستجو
    search = request.GET.get('q', '').strip()
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search)
        )

    # فیلتر نقش
    role_filter = request.GET.get('role', '')
    if role_filter:
        if role_filter == 'admin':
            users = users.filter(is_superuser=True)
        elif role_filter == 'none':
            users = users.filter(is_superuser=False, groups__isnull=True)
        elif role_filter == 'inactive':
            users = users.filter(is_active=False)
        elif role_filter == 'active':
            users = users.filter(is_active=True)
        else:
            from .forms import ROLE_GROUP_MAP
            group_name = ROLE_GROUP_MAP.get(role_filter, '')
            if group_name:
                users = users.filter(groups__name=group_name)

    # آمار
    stats = {
        'total': User.objects.count(),
        'active': User.objects.filter(is_active=True).count(),
        'inactive': User.objects.filter(is_active=False).count(),
        'admins': User.objects.filter(is_superuser=True).count(),
    }

    paginator = Paginator(users, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # برای هر کاربر، نقش نمایش داده شود
    users_data = []
    for u in page_obj:
        users_data.append({
            'user': u,
            'role_display': dict([
                ('admin', 'مدیر کل'),
                ('sales_manager', 'مدیر فروش'),
                ('sales', 'کارشناس فروش'),
                ('support', 'پشتیبان'),
                ('accountant', 'حسابدار'),
                ('operator', 'اپراتور'),
                ('none', 'بدون نقش خاص'),
            ]).get(get_user_role(u), '—'),
            'role_key': get_user_role(u),
        })

    context = {
        'users_data': users_data,
        'stats': stats,
        'search': search,
        'current_role': role_filter,
        'role_choices': [
            ('', 'همه'),
            ('admin', 'مدیر کل'),
            ('sales_manager', 'مدیر فروش'),
            ('sales', 'کارشناس فروش'),
            ('support', 'پشتیبان'),
            ('accountant', 'حسابدار'),
            ('operator', 'اپراتور'),
            ('none', 'بدون نقش'),
            ('active', 'فعال'),
            ('inactive', 'غیرفعال'),
        ],
    }
    return render(request, 'accounts/user_list.html', context)


@login_required
@require_permission('accounts.manage_users')
def user_create(request):
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'کاربر «{user.username}» با موفقیت ساخته شد.')
            return redirect('accounts:user_list')
    else:
        form = UserCreateForm()

    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': 'ایجاد کاربر جدید',
        'submit_label': 'ایجاد کاربر',
        'is_create': True,
    })


@login_required
@require_permission('accounts.manage_users')
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            # اگه داره خودش رو غیرفعال می‌کنه، اجازه نده
            if user == request.user and not form.cleaned_data.get('is_active'):
                messages.error(request, 'نمی‌توانید حساب خودتان را غیرفعال کنید.')
                return redirect('accounts:user_edit', pk=pk)

            # اگه داره نقش خودش رو از مدیر کل عوض می‌کنه، اجازه نده
            if user == request.user and form.cleaned_data.get('role') != 'admin':
                messages.error(request, 'نمی‌توانید نقش خودتان را از مدیر کل تغییر دهید.')
                return redirect('accounts:user_edit', pk=pk)

            form.save()
            messages.success(request, 'اطلاعات کاربر به‌روزرسانی شد.')
            return redirect('accounts:user_list')
    else:
        form = UserEditForm(instance=user)

    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': f'ویرایش کاربر: {user.username}',
        'submit_label': 'ذخیره تغییرات',
        'is_create': False,
        'user_obj': user,
        'is_self': user == request.user,
    })


@login_required
@require_permission('accounts.manage_users')
def user_password(request, pk):
    user = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        form = UserPasswordForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data['password1'])
            user.save()
            messages.success(request, f'رمز کاربر «{user.username}» تغییر کرد.')
            return redirect('accounts:user_list')
    else:
        form = UserPasswordForm()

    return render(request, 'accounts/user_password.html', {
        'form': form,
        'user_obj': user,
    })


@login_required
@require_permission('accounts.manage_users')
def user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)

    # جلوگیری از حذف خود
    if user == request.user:
        messages.error(request, 'نمی‌توانید حساب خودتان را حذف کنید.')
        return redirect('accounts:user_list')

    # ⭐ چک ارتباط‌های مهم — اگه کاربر داده‌ی مرتبط داره، حذف نکن
    blockers = []

    if hasattr(user, 'employee_profile'):
        blockers.append(f'پروفایل پرسنلی «{user.employee_profile.full_name}»')

    calls_count = user.calls.count()
    if calls_count:
        blockers.append(f'{calls_count} تماس انجام‌شده')

    created_calls_count = user.created_calls.count()
    if created_calls_count:
        blockers.append(f'{created_calls_count} تماس ثبت‌شده')

    invoices_count = user.created_invoices.count()
    if invoices_count:
        blockers.append(f'{invoices_count} فاکتور صادرشده')

    customers_count = user.created_customers.count()
    if customers_count:
        blockers.append(f'{customers_count} مشتری ثبت‌شده')

    tasks_count = user.created_tasks.count()
    if tasks_count:
        blockers.append(f'{tasks_count} وظیفه ایجادشده')

    leaves_count = user.reviewed_leaves.count()
    if leaves_count:
        blockers.append(f'{leaves_count} مرخصی بررسی‌شده')

    if blockers:
        messages.error(
            request,
            f'این کاربر دارای {", ".join(blockers)} است و قابل حذف نیست. '
            'برای قطع دسترسی، از گزینه‌ی «غیرفعال‌سازی» استفاده کنید.'
        )
        return redirect('accounts:user_list')

    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f'کاربر «{username}» حذف شد.')
        return redirect('accounts:user_list')

    return render(request, 'accounts/confirm_delete.html', {'user_obj': user})


@login_required
@require_permission('accounts.manage_users')
def user_toggle_active(request, pk):
    user = get_object_or_404(User, pk=pk)

    if user == request.user:
        messages.error(request, 'نمی‌توانید حساب خودتان را غیرفعال کنید.')
        return redirect('accounts:user_list')

    if request.method == 'POST':
        user.is_active = not user.is_active
        user.save()
        status = 'فعال' if user.is_active else 'غیرفعال'
        messages.success(request, f'کاربر «{user.username}» {status} شد.')
    return redirect('accounts:user_list')