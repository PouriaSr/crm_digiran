"""
ماژول مرکزی کنترل دسترسی نقش‌محور (RBAC)

این فایل تنها منبع حقیقت برای:
- تعریف نقش‌ها
- تعریف دسترسی‌ها
- نگاشت نقش به دسترسی
- توابع کمکی برای Viewها و تمپلیت‌ها
"""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


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

    # ─── دسته‌بندی‌ها ⭐ جدید ───
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

    # ─── مدیریت کاربران ───
    'accounts.manage_users': [ROLE_ADMIN],
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
# Decoratorها
# ═══════════════════════════════════════════════════════════
def require_roles(*roles, redirect_to='dashboard:home'):
    """Decorator: کاربر باید یکی از این نقش‌ها رو داشته باشه."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            if has_role(request.user, *roles):
                return view_func(request, *args, **kwargs)
            messages.error(request, 'شما دسترسی به این بخش را ندارید.')
            return redirect(redirect_to)
        return wrapper
    return decorator


def require_permission(permission_name, redirect_to='dashboard:home'):
    """Decorator: کاربر باید این دسترسی خاص رو داشته باشه."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            if has_permission(request.user, permission_name):
                return view_func(request, *args, **kwargs)
            messages.error(request, 'شما دسترسی به این بخش را ندارید.')
            return redirect(redirect_to)
        return wrapper
    return decorator