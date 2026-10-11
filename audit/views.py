import jdatetime
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from accounts.permissions import require_permission
from .models import AuditLog


def _parse_jalali_date(value):
    """تبدیل تاریخ شمسی به میلادی — None اگه نامعتبر بود"""
    if not value:
        return None
    try:
        persian = '۰۱۲۳۴۵۶۷۸۹'
        arabic = '٠١٢٣٤٥٦٧٨٩'
        for i, (p, a) in enumerate(zip(persian, arabic)):
            value = value.replace(p, str(i)).replace(a, str(i))
        value = value.replace('-', '/').replace('.', '/')
        if ' ' in value:
            value = value.split(' ', 1)[0]
        y, m, d = map(int, value.split('/'))
        return jdatetime.date(y, m, d).togregorian()
    except (ValueError, AttributeError):
        return None


@login_required
@require_permission('audit.view')
def audit_log_list(request):
    """لیست لاگ‌های سیستم با فیلتر"""
    logs = AuditLog.objects.select_related('user', 'content_type').all()

    # ─── فیلترها ───
    action = request.GET.get('action', '').strip()
    if action:
        logs = logs.filter(action=action)

    model_name = request.GET.get('model', '').strip()
    if model_name:
        logs = logs.filter(model_name=model_name)

    user_id = request.GET.get('user', '').strip()
    if user_id:
        logs = logs.filter(user_id=user_id)

    search = request.GET.get('q', '').strip()
    if search:
        logs = logs.filter(
            Q(object_repr__icontains=search) |
            Q(description__icontains=search)
        )

    from_date_str = request.GET.get('from_date', '').strip()
    to_date_str = request.GET.get('to_date', '').strip()
    from_date = _parse_jalali_date(from_date_str)
    to_date = _parse_jalali_date(to_date_str)
    if from_date:
        logs = logs.filter(created_at__date__gte=from_date)
    if to_date:
        logs = logs.filter(created_at__date__lte=to_date)

    has_filters = any([action, model_name, user_id, search, from_date_str, to_date_str])

    # ─── آمار ───
    total = AuditLog.objects.count()
    today = jdatetime.date.today().togregorian()
    stats = {
        'total': total,
        'today': AuditLog.objects.filter(created_at__date=today).count(),
        'created': AuditLog.objects.filter(action='created').count(),
        'updated': AuditLog.objects.filter(action='updated').count(),
        'deleted': AuditLog.objects.filter(action='deleted').count(),
    }

    # ─── dropdowns ───
    models_list = (
        AuditLog.objects.values_list('model_name', 'verbose_name')
        .distinct().order_by('verbose_name')
    )
    users_list = User.objects.filter(
        audit_logs__isnull=False
    ).distinct().order_by('first_name', 'last_name', 'username')

    paginator = Paginator(logs, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'page_obj': page_obj,
        'stats': stats,
        'action_choices': AuditLog.ACTION_CHOICES,
        'models_list': models_list,
        'users_list': users_list,
        'current_action': action,
        'current_model': model_name,
        'current_user': user_id,
        'search': search,
        'from_date': from_date_str,
        'to_date': to_date_str,
        'has_filters': has_filters,
        'filtered_count': logs.count() if has_filters else None,
    }
    return render(request, 'audit/log_list.html', context)