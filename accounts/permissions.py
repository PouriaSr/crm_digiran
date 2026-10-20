"""
ماژول مرکزی کنترل دسترسی نقش‌محور (RBAC)
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
ROLE_ADS_MANAGER = 'ads_manager'

ROLE_DISPLAY = {
    ROLE_ADMIN: 'مدیر کل',
    ROLE_SALES_MANAGER: 'مدیر فروش',
    ROLE_SALES: 'کارشناس فروش',
    ROLE_SUPPORT: 'پشتیبان',
    ROLE_ACCOUNTANT: 'حسابدار',
    ROLE_OPERATOR: 'اپراتور',
    ROLE_ADS_MANAGER: 'مسئول تبلیغات',
}

ROLE_TO_GROUP = {
    ROLE_SALES_MANAGER: 'مدیر فروش',
    ROLE_SALES: 'کارشناس فروش',
    ROLE_SUPPORT: 'پشتیبان',
    ROLE_ACCOUNTANT: 'حسابدار',
    ROLE_OPERATOR: 'اپراتور',
    ROLE_ADS_MANAGER: 'مسئول تبلیغات',
}


# ═══════════════════════════════════════════════════════════
# تعریف دسترسی‌ها
# ═══════════════════════════════════════════════════════════
PERMISSIONS = {
    'customers.view':   [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_OPERATOR, ROLE_ADS_MANAGER],
    'customers.add':    [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_OPERATOR],
    'customers.edit':   [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_OPERATOR],
    'customers.delete': [ROLE_ADMIN, ROLE_SALES_MANAGER],
    'customers.visit': [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_OPERATOR],
    'customers.followup': [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT],

    'calls.view':       [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_OPERATOR, ROLE_ADS_MANAGER],
    'calls.add':        [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_OPERATOR],
    'calls.edit':       [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT],
    'calls.delete':     [ROLE_ADMIN, ROLE_SALES_MANAGER],
    'calls.reassign':   [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT],

    'products.view':    [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_OPERATOR, ROLE_ADS_MANAGER],
    'products.add':     [ROLE_ADMIN, ROLE_SALES_MANAGER],
    'products.edit':    [ROLE_ADMIN, ROLE_SALES_MANAGER],
    'products.delete':  [ROLE_ADMIN],

    'categories.view':   [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_OPERATOR, ROLE_ADS_MANAGER],
    'categories.manage': [ROLE_ADMIN, ROLE_SALES_MANAGER],

    'invoices.view':    [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_ADS_MANAGER],
    'invoices.add':     [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_ACCOUNTANT],
    'invoices.edit':    [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_ACCOUNTANT],
    'invoices.delete':  [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_ACCOUNTANT],
    'invoices.print':   [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_ADS_MANAGER],

    'hr.view_employees':    [ROLE_ADMIN, ROLE_SALES_MANAGER],
    'hr.manage_employees':  [ROLE_ADMIN],
    'hr.view_tasks':        [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_OPERATOR, ROLE_ADS_MANAGER],
    'hr.manage_tasks':      [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES],
    'hr.review_leaves':     [ROLE_ADMIN, ROLE_SALES_MANAGER],
    'hr.attendance':        [ROLE_ADMIN, ROLE_SALES_MANAGER],

    'dashboard.view':   [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_OPERATOR, ROLE_ADS_MANAGER],
    'dashboard.export': [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_ACCOUNTANT],
    'dashboard.bi':     [ROLE_ADMIN, ROLE_SALES_MANAGER],

    'accounts.manage_users': [ROLE_ADMIN],
    'audit.view':            [ROLE_ADMIN],

    'ads.view':        [ROLE_ADMIN, ROLE_ADS_MANAGER],
    'ads.add':         [ROLE_ADMIN, ROLE_ADS_MANAGER],
    'ads.edit':        [ROLE_ADMIN, ROLE_ADS_MANAGER],
    'ads.delete':      [ROLE_ADMIN],
    'ads.manage_defs': [ROLE_ADMIN],
}


# ─── متادیتای نمایش دسترسی‌ها ───
PERMISSION_META = {
    'customers.view':   ('مشتریان', 'مشاهده', 'مشاهده‌ی لیست و جزئیات مشتریان'),
    'customers.add':    ('مشتریان', 'ایجاد', 'افزودن مشتری جدید'),
    'customers.edit':   ('مشتریان', 'ویرایش', 'ویرایش اطلاعات مشتریان'),
    'customers.delete': ('مشتریان', 'حذف', 'غیرفعال‌سازی و بازگردانی مشتریان'),

    'calls.view':     ('تماس‌ها', 'مشاهده', 'مشاهده‌ی لیست و جزئیات تماس‌ها'),
    'calls.add':      ('تماس‌ها', 'ایجاد', 'ثبت تماس جدید'),
    'calls.edit':     ('تماس‌ها', 'ویرایش', 'ویرایش تماس‌ها'),
    'calls.delete':   ('تماس‌ها', 'حذف', 'حذف تماس'),
    'calls.reassign': ('تماس‌ها', 'ارجاع', 'ارجاع تماس به کارمند دیگر'),

    'products.view':   ('کالاها', 'مشاهده', 'مشاهده‌ی لیست و جزئیات کالاها'),
    'products.add':    ('کالاها', 'ایجاد', 'افزودن کالای جدید'),
    'products.edit':   ('کالاها', 'ویرایش', 'ویرایش اطلاعات کالاها'),
    'products.delete': ('کالاها', 'حذف', 'حذف نرم کالاها'),

    'categories.view':   ('دسته‌بندی‌ها', 'مشاهده', 'مشاهده‌ی دسته‌بندی‌ها'),
    'categories.manage': ('دسته‌بندی‌ها', 'مدیریت', 'ایجاد، ویرایش و حذف دسته‌بندی'),

    'invoices.view':   ('فاکتورها', 'مشاهده', 'مشاهده‌ی لیست و جزئیات فاکتورها'),
    'invoices.add':    ('فاکتورها', 'ایجاد', 'صدور فاکتور جدید'),
    'invoices.edit':   ('فاکتورها', 'ویرایش', 'ویرایش فاکتورها'),
    'invoices.delete': ('فاکتورها', 'حذف', 'حذف فاکتورها'),
    'invoices.print':  ('فاکتورها', 'چاپ', 'چاپ فاکتور'),

    'hr.view_employees':   ('منابع انسانی', 'مشاهده پرسنل', 'مشاهده‌ی لیست و جزئیات پرسنل'),
    'hr.manage_employees': ('منابع انسانی', 'مدیریت پرسنل', 'افزودن، ویرایش و حذف پرسنل'),
    'hr.view_tasks':       ('منابع انسانی', 'مشاهده وظایف', 'مشاهده‌ی وظایف (غیرمدیر فقط وظایف خودش)'),
    'hr.manage_tasks':     ('منابع انسانی', 'مدیریت وظایف', 'افزودن، ویرایش و حذف وظایف همه‌ی کارمندان'),
    'hr.review_leaves':    ('منابع انسانی', 'بررسی مرخصی', 'تایید یا رد درخواست‌های مرخصی'),
    'hr.attendance':       ('منابع انسانی', 'حضور و غیاب', 'ثبت و گزارش حضور و غیاب'),

    'dashboard.view':   ('داشبورد و گزارش', 'مشاهده داشبورد', 'دسترسی به صفحه‌ی اصلی داشبورد'),
    'dashboard.export': ('داشبورد و گزارش', 'خروجی Excel', 'دانلود گزارش به فرمت Excel'),
    'dashboard.bi':     ('داشبورد و گزارش', 'گزارش‌های BI', 'گزارش‌های تحلیلی پیشرفته'),

    'accounts.manage_users': ('سیستم', 'مدیریت کاربران', 'افزودن، ویرایش و حذف کاربران و تعیین نقش'),
    'audit.view':            ('سیستم', 'لاگ سیستم', 'مشاهده‌ی لاگ تغییرات مدل‌های حساس'),

    'ads.view':        ('تبلیغات', 'مشاهده', 'مشاهده‌ی تبلیغات (غیرمدیر فقط تبلیغات خودش)'),
    'ads.add':         ('تبلیغات', 'ایجاد', 'ثبت تبلیغ جدید'),
    'ads.edit':        ('تبلیغات', 'ویرایش', 'ویرایش تبلیغات'),
    'ads.delete':      ('تبلیغات', 'حذف', 'حذف تبلیغات'),
    'ads.manage_defs': ('تبلیغات', 'مدیریت تعاریف', 'مدیریت پلتفرم‌ها، فرآیندها و منابع'),
}


# ═══════════════════════════════════════════════════════════
# توابع کمکی
# ═══════════════════════════════════════════════════════════
def get_user_role(user):
    """
    نقش کاربر رو از روی عضویت گروهی برمی‌گردونه.

    ترتیب چک:
    1. Superuser → admin
    2. گروه فارسی (طبق ROLE_TO_GROUP) → role_key
    3. گروه انگلیسی (legacy/تست) → role_key (fallback)
    """
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return ROLE_ADMIN

    # ─── چک گروه فارسی ───
    for role_key, group_name in ROLE_TO_GROUP.items():
        if user.groups.filter(name=group_name).exists():
            return role_key

    # ─── fallback: چک گروه انگلیسی (برای سازگاری با تست‌ها/legacy) ───
    for role_key in ROLE_TO_GROUP.keys():
        if user.groups.filter(name=role_key).exists():
            return role_key

    return 'none'


def get_user_role_display(user):
    role = get_user_role(user)
    return ROLE_DISPLAY.get(role, '—')


def has_role(user, *roles):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return get_user_role(user) in roles


def has_permission(user, permission_name):
    """
    ترتیب:
    1. سوپریوزر → True
    2. override کاربر → granted یا denied
    3. نقش کاربر → از PERMISSIONS
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    # 1. override
    override = user.permission_overrides.filter(
        permission_key=permission_name,
    ).first()
    if override is not None:
        return override.granted

    # 2. role-based
    allowed_roles = PERMISSIONS.get(permission_name, [])
    return get_user_role(user) in allowed_roles


def get_user_permissions(user):
    if not user or not user.is_authenticated:
        return set()
    if user.is_superuser:
        return set(PERMISSIONS.keys())

    user_role = get_user_role(user)
    perms = {
        perm for perm, roles in PERMISSIONS.items()
        if user_role in roles
    }

    for override in user.permission_overrides.all():
        if override.granted:
            perms.add(override.permission_key)
        else:
            perms.discard(override.permission_key)

    return perms


# ═══════════════════════════════════════════════════════════
# Handling denial
# ═══════════════════════════════════════════════════════════
def _is_ajax(request):
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.headers.get('HX-Request') == 'true'
    )


def _log_denied(request, permission_name):
    user = getattr(request, 'user', None)
    username = (
        user.username if user and user.is_authenticated else 'anonymous'
    )
    logger.warning(
        'Access denied — user=%s permission=%s path=%s method=%s',
        username, permission_name, request.path, request.method,
    )


def _render_403(request, message=None):
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
    _log_denied(request, permission_name)

    if _is_ajax(request):
        return JsonResponse({
            'success': False,
            'error': 'شما دسترسی به این عملیات را ندارید.',
        }, status=403)

    if on_denied == 'redirect':
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return redirect(redirect_to)

    return _render_403(request)


# ═══════════════════════════════════════════════════════════
# Decoratorها
# ═══════════════════════════════════════════════════════════
def require_roles(*roles, on_denied='403', redirect_to='dashboard:home'):
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