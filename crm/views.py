"""
Views سطح پروژه — error handlers و صفحات سیستمی
"""
import logging
from django.shortcuts import render

logger = logging.getLogger('crm.security')


# ═══════════════════════════════════════════════════════════
# Error handler — 403
# ═══════════════════════════════════════════════════════════
def custom_403_view(request, exception=None):
    """
    صفحه‌ی سفارشی 403 — دسترسی رد شد.
    توسط handler403 در crm/urls.py صدا زده می‌شه.
    """
    message = None
    if exception is not None:
        msg = getattr(exception, 'message', None) or str(exception)
        if msg and msg not in ('', 'Forbidden', 'PermissionDenied'):
            message = msg

    user = getattr(request, 'user', None)
    username = (
        user.username if user and user.is_authenticated else 'anonymous'
    )
    logger.warning(
        'Permission denied — user=%s path=%s method=%s referer=%s',
        username,
        request.path,
        request.method,
        request.META.get('HTTP_REFERER', '—'),
    )

    return render(request, 'errors/403.html', {
        'message': message,
    }, status=403)