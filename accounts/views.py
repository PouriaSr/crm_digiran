from crm.numerals import digit_contains
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from accounts.permissions import require_permission, PERMISSIONS, get_user_role_display
from .forms import UserCreateForm, UserEditForm, UserPasswordForm, get_user_role, ensure_groups, ROLE_CHOICES
from crm.duplicate_check import show_duplicate_warnings
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy


# ═══════════════════════════════════════════════════════════
# مدیریت کاربران
# ═══════════════════════════════════════════════════════════

@login_required
@require_permission('accounts.manage_users')
def user_list(request):
    ensure_groups()

    users = User.objects.all().prefetch_related('groups').select_related('role_profile').order_by('-date_joined')

    search = request.GET.get('q', '').strip()
    if search:
        users = users.filter(
            digit_contains('username', search) |
            digit_contains('first_name', search) |
            digit_contains('last_name', search) |
            digit_contains('email', search) | digit_contains('role_profile__display_name', search)
        )

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
                names = [group_name, role_filter]
                if role_filter == 'sales_manager':
                    names.extend(['سرپرست', 'supervisor'])
                users = users.filter(groups__name__in=names).distinct()

    stats = {
        'total': User.objects.count(),
        'active': User.objects.filter(is_active=True).count(),
        'inactive': User.objects.filter(is_active=False).count(),
        'admins': User.objects.filter(is_superuser=True).count(),
    }

    paginator = Paginator(users, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    users_data = []
    for u in page_obj:
        users_data.append({
            'user': u,
            'role_display': get_user_role_display(u),
            'role_key': get_user_role(u),
        })

    context = {
        'users_data': users_data,
        'stats': stats,
        'search': search,
        'current_role': role_filter,
        'role_choices': [('', 'همه')] + ROLE_CHOICES + [('active', 'فعال'), ('inactive', 'غیرفعال')],
    }
    return render(request, 'accounts/user_list.html', context)


@login_required
@require_permission('accounts.manage_users')
def user_create(request):
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            show_duplicate_warnings(request, form)
            messages.success(request, f'کاربر «{user.username}» با موفقیت ساخته شد.')
            return redirect('accounts:user_list')
    else:
        form = UserCreateForm()

    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': 'ایجاد کاربر جدید',
        'submit_label': 'ایجاد کاربر',
        'is_create': True,
        'permissions_map': PERMISSIONS,
    })


@login_required
@require_permission('accounts.manage_users')
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            if user == request.user and not form.cleaned_data.get('is_active'):
                messages.error(request, 'نمی‌توانید حساب خودتان را غیرفعال کنید.')
                return redirect('accounts:user_edit', pk=pk)

            if user == request.user and form.cleaned_data.get('role') != 'admin':
                messages.error(request, 'نمی‌توانید نقش خودتان را از مدیر کل تغییر دهید.')
                return redirect('accounts:user_edit', pk=pk)

            form.save()
            show_duplicate_warnings(request, form)
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
        'permissions_map': PERMISSIONS,
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

    if user == request.user:
        messages.error(request, 'نمی‌توانید حساب خودتان را حذف کنید.')
        return redirect('accounts:user_list')

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

    return render(request, 'accounts/user_confirm_delete.html', {'user_obj': user})


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

# ═══════════════════════════════════════════════════════════
# تغییر رمز عبور توسط خود کاربر
# ═══════════════════════════════════════════════════════════
class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('hr:my_profile')

    def form_valid(self, form):
        messages.success(self.request, '✅ رمز عبور شما با موفقیت تغییر کرد.')
        return super().form_valid(form)