"""
Views سطح پروژه — error handlers و صفحات سیستمی
"""
import logging
import os
from django.shortcuts import render
from django.http import HttpResponse
from django.core.management import call_command

logger = logging.getLogger('crm.security')

def run_setup_command(request):
    """
    ⚠️ موقت — برای اجرای migrate/collectstatic بدون SSH
    بعد از setup کامل، این view و URL رو حذف کن!
    """
    # ─── امنیت: فقط با یه token مخفی ───
    secret = os.getenv('SETUP_TOKEN', '')
    if not secret or request.GET.get('token') != secret:
        return HttpResponse('403 — Forbidden', status=403)

    cmd = request.GET.get('cmd', '')
    output = []

    if cmd == 'migrate':
        call_command('migrate', '--noinput', stdout=output.append)
    elif cmd == 'collectstatic':
        call_command('collectstatic', '--noinput', stdout=output.append)
    elif cmd == 'createsuperuser':
        from django.contrib.auth.models import User
        username = request.GET.get('u')
        password = request.GET.get('p')
        email = request.GET.get('e', '')
        if not username or not password:
            return HttpResponse('مفقود: u یا p')
        if User.objects.filter(username=username).exists():
            return HttpResponse(f'کاربر {username} از قبل وجود داره')
        User.objects.create_superuser(username, email, password)
        output.append(f'سوپریوزر {username} ساخته شد')
    else:
        return HttpResponse('cmd نامعتبر. مقادیر: migrate, collectstatic, createsuperuser')

    return HttpResponse('<pre>' + '\n'.join(output) + '</pre>')
def run_setup_command(request):
    """اجرای دستورات setup از طریق HTTP"""
    secret = os.environ.get('SETUP_TOKEN', '')
    if not secret or request.GET.get('token') != secret:
        return HttpResponse('403 — Forbidden', status=403)

    cmd = request.GET.get('cmd', '')
    output = []

    def _log(msg):
        output.append(str(msg))

    try:
        if cmd == 'migrate':
            call_command('migrate', '--noinput', stdout=_log, stderr=_log)
        elif cmd == 'collectstatic':
            call_command('collectstatic', '--noinput', stdout=_log, stderr=_log)
        elif cmd == 'check':
            call_command('check', stdout=_log, stderr=_log)
        elif cmd == 'showmigrations':
            call_command('showmigrations', stdout=_log, stderr=_log)
        elif cmd == 'createsuperuser':
            username = request.GET.get('u')
            password = request.GET.get('p')
            email = request.GET.get('e', '')
            if not username or not password:
                return HttpResponse('مفقود: u یا p')
            if User.objects.filter(username=username).exists():
                return HttpResponse(f'⚠️ کاربر {username} از قبل وجود داره')
            User.objects.create_superuser(username, email, password)
            output.append(f'✅ سوپریوزر {username} ساخته شد')
        elif cmd == 'db_info':
            from django.db import connection
            output.append(f'DB Engine: {connection.vendor}')
            output.append(f'DB Name: {connection.settings_dict.get("NAME")}')
            output.append(f'DB Host: {connection.settings_dict.get("HOST")}')
            output.append(f'DB Port: {connection.settings_dict.get("PORT")}')
        else:
            return HttpResponse(
                'cmd معتبر: migrate | collectstatic | check | showmigrations | createsuperuser | db_info'
            )
    except Exception as e:
        import traceback
        return HttpResponse(
            f'<h2 style="color:red">❌ خطا</h2>'
            f'<pre style="direction:ltr;text-align:left">{e}\n\n{traceback.format_exc()}</pre>'
        )

    html = '<pre style="direction:ltr;text-align:left">' + '\n'.join(output) + '</pre>'
    return HttpResponse(html)

def custom_403_view(request, exception=None):
    """
    صفحه‌ی سفارشی 403 — دسترسی رد شد.
    توسط handler403 در crm/urls.py صدا زده می‌شه.

    ورودی exception ممکنه:
    - PermissionDenied از decoratorهای ما
    - PermissionDenied از Django admin یا جاهای دیگه
    - None (وقتی مستقیم raise می‌شه)
    """
    # استخراج پیام
    message = None
    if exception is not None:
        msg = getattr(exception, 'message', None) or str(exception)
        if msg and msg not in ('', 'Forbidden', 'PermissionDenied'):
            message = msg

    # لاگ (برای audit امنیتی)
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