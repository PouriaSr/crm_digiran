"""
ماژول مرکزی کنترل دسترسی نقش‌محور (RBAC)

این فایل تنها منبع حقیقت برای:
- تعریف نقش‌ها
- تعریف دسترسی‌ها
- نگاشت نقش به دسترسی
- توابع کمکی برای Viewها و تمپلیت‌ها
"""
import logging
from functools import wraps

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render


logger = logging.getLogger('crm.security')


# ═══════════════════════════════════════════════════════════
# نقش‌ها
# ═══════════════════════════════════════════════════════════
ROLE_ADMIN = 'admin'
ROLE_SALES_MANAGER = 'sales_manager'
ROLE_SALES = 'sales'
ROLE_SUPPORT = 'support'
ROLE_ACCOUNTANT = 'accountant'
ROLE_OPERATOR = 'operator'

ROLE_DISPLAY = {
    ROLE_ADMIN: 'مدیر کل',
    ROLE_SALES_MANAGER: 'مدیر فروش',
    ROLE_SALES: 'کارشناس فروش',
    ROLE_SUPPORT: 'پشتیبان',
    ROLE_ACCOUNTANT: 'حسابدار',
    ROLE_OPERATOR: 'اپراتور',
}

ROLE_TO_GROUP = {
    ROLE_SALES_MANAGER: 'مدیر فروش',
    ROLE_SALES: 'کارشناس فروش',
    ROLE_SUPPORT: 'پشتیبان',
    ROLE_ACCOUNTANT: 'حسابدار',
    ROLE_OPERATOR: 'اپراتور',
}


# ═══════════════════════════════════════════════════════════
# تعریف دسترسی‌ها
# ═══════════════════════════════════════════════════════════
PERMISSIONS = {
    # ─── مشتریان ───
    'customers.view':   [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_OPERATOR],
    'customers.add':    [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_OPERATOR],
    'customers.edit':   [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_OPERATOR],
    'customers.delete': [ROLE_ADMIN, ROLE_SALES_MANAGER],

    # ─── تماس‌ها ───
    'calls.view':       [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_OPERATOR],
    'calls.add':        [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_OPERATOR],
    'calls.edit':       [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_OPERATOR],
    'calls.delete':     [ROLE_ADMIN, ROLE_SALES_MANAGER],
    'calls.reassign':   [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT],

    # ─── کالاها ───
    'products.view':    [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_OPERATOR],
    'products.add':     [ROLE_ADMIN, ROLE_SALES_MANAGER],
    'products.edit':    [ROLE_ADMIN, ROLE_SALES_MANAGER],
    'products.delete':  [ROLE_ADMIN],

    # ─── دسته‌بندی‌ها ───
    'categories.view':   [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_OPERATOR],
    'categories.manage': [ROLE_ADMIN, ROLE_SALES_MANAGER],

    # ─── فاکتورها ───
    'invoices.view':    [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_ACCOUNTANT],
    'invoices.add':     [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_ACCOUNTANT],
    'invoices.edit':    [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_ACCOUNTANT],
    'invoices.delete':  [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_ACCOUNTANT],
    'invoices.print':   [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_ACCOUNTANT],

    # ─── منابع انسانی ───
    'hr.view_employees':    [ROLE_ADMIN, ROLE_SALES_MANAGER],
    'hr.manage_employees':  [ROLE_ADMIN],
    'hr.view_tasks':        [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT],
    'hr.manage_tasks':      [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT],
    'hr.review_leaves':     [ROLE_ADMIN, ROLE_SALES_MANAGER],
    'hr.attendance':        [ROLE_ADMIN, ROLE_SALES_MANAGER],

    # ─── داشبورد و گزارش ───
    'dashboard.view':   [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_OPERATOR],
    'dashboard.export': [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_ACCOUNTANT],
    'dashboard.bi':     [ROLE_ADMIN, ROLE_SALES_MANAGER],

    # ─── مدیریت کاربران ───
    'accounts.manage_users': [ROLE_ADMIN],
    # ─── لاگ سیستم ───
    'audit.view': [ROLE_ADMIN],
}


# ═══════════════════════════════════════════════════════════
# توابع کمکی
# ═══════════════════════════════════════════════════════════
def get_user_role(user):
    """تشخیص نقش فعلی کاربر"""
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return ROLE_ADMIN
    for role_key, group_name in ROLE_TO_GROUP.items():
        if user.groups.filter(name=group_name).exists():
            return role_key
    return 'none'


def get_user_role_display(user):
    """نام نمایشی نقش کاربر"""
    role = get_user_role(user)
    return ROLE_DISPLAY.get(role, '—')


def has_role(user, *roles):
    """آیا کاربر یکی از نقش‌های داده‌شده رو داره؟"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return get_user_role(user) in roles


def has_permission(user, permission_name):
    """آیا کاربر این دسترسی خاص رو داره؟"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    allowed_roles = PERMISSIONS.get(permission_name, [])
    return get_user_role(user) in allowed_roles


def get_user_permissions(user):
    """مجموعه‌ی همه‌ی دسترسی‌های کاربر"""
    if not user or not user.is_authenticated:
        return set()
    if user.is_superuser:
        return set(PERMISSIONS.keys())
    user_role = get_user_role(user)
    return {
        perm for perm, roles in PERMISSIONS.items()
        if user_role in roles
    }


# ═══════════════════════════════════════════════════════════
# توابع داخلی — handling denial (۸.۱)
# ═══════════════════════════════════════════════════════════
def _is_ajax(request):
    """آیا درخواست AJAX/HTMX هست؟"""
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.headers.get('HX-Request') == 'true'
    )


def _log_denied(request, permission_name):
    """ثبت تلاش غیرمجاز در لاگ امنیتی"""
    user = getattr(request, 'user', None)
    username = (
        user.username if user and user.is_authenticated else 'anonymous'
    )
    logger.warning(
        'Access denied — user=%s permission=%s path=%s method=%s',
        username,
        permission_name,
        request.path,
        request.method,
    )


def _render_403(request, message=None):
    """
    رندر صفحه‌ی 403 با context کامل.
    مستقیماً response برمی‌گردونه (نه raise) تا در unit test هم کار کنه.
    """
    user = getattr(request, 'user', None)
    user_role_display = (
        get_user_role_display(user)
        if user and user.is_authenticated else None
    )
    return render(request, 'errors/403.html', {
        'message': message or 'شما دسترسی به این بخش را ندارید.',
        'user_role_display': user_role_display,
    }, status=403)


def _handle_denied(request, permission_name, on_denied, redirect_to):
    """
    رفتار در صورت رد دسترسی.

    on_denied:
      - '403'      → صفحه 403 (پیش‌فرض جدید)
      - 'redirect' → پیام + ریدایرکت به داشبورد (رفتار قدیم)
    """
    _log_denied(request, permission_name)

    # AJAX → همیشه JSON
    if _is_ajax(request):
        return JsonResponse({
            'success': False,
            'error': 'شما دسترسی به این عملیات را ندارید.',
        }, status=403)

    # redirect (legacy)
    if on_denied == 'redirect':
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return redirect(redirect_to)

    # default → 403
    return _render_403(request)


# ═══════════════════════════════════════════════════════════
# Decoratorها
# ═══════════════════════════════════════════════════════════
def require_roles(*roles, on_denied='403', redirect_to='dashboard:home'):
    """
    Decorator: کاربر باید یکی از این نقش‌ها رو داشته باشه.

    پارامترها:
      - roles: نقش‌های مجاز
      - on_denied: '403' (پیش‌فرض) یا 'redirect'
      - redirect_to: URL name در حالت redirect
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if _is_ajax(request):
                    return JsonResponse(
                        {'success': False, 'error': 'لطفاً وارد شوید.'},
                        status=401,
                    )
                return redirect('accounts:login')

            if has_role(request.user, *roles):
                return view_func(request, *args, **kwargs)

            return _handle_denied(
                request,
                permission_name=f'roles={roles}',
                on_denied=on_denied,
                redirect_to=redirect_to,
            )
        return wrapper
    return decorator


def require_permission(permission_name, on_denied='403', redirect_to='dashboard:home'):
    """
    Decorator: کاربر باید این دسترسی خاص رو داشته باشه.

    پارامترها:
      - permission_name: نام دسترسی (مثلاً 'customers.view')
      - on_denied: '403' (پیش‌فرض جدید) یا 'redirect' (رفتار قدیم)
      - redirect_to: URL name در حالت redirect
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if _is_ajax(request):
                    return JsonResponse(
                        {'success': False, 'error': 'لطفاً وارد شوید.'},
                        status=401,
                    )
                return redirect('accounts:login')

            if has_permission(request.user, permission_name):
                return view_func(request, *args, **kwargs)

            return _handle_denied(
                request,
                permission_name=permission_name,
                on_denied=on_denied,
                redirect_to=redirect_to,
            )
        return wrapper
    return decorator