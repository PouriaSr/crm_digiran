"""
Views احراز هویت سفارشی — ۸.۲
"""
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect

from .ratelimit import (
    get_client_ip,
    is_locked,
    register_failure,
    clear_failures,
    get_lock_remaining,
)


class RateLimitedLoginView(LoginView):
    """
    LoginView با محافظت brute-force.

    - پس از N تلاش ناموفق → قفل موقت
    - لاگین موفق → پاک کردن شمارنده‌ها
    - پیام فارسی با زمان باقی‌مانده
    """
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        username = request.POST.get('username', '').strip()
        ip = get_client_ip(request)

        # ─── ۱. آیا کاربر/IP قفل هست؟ ───
        if is_locked(username, ip):
            remaining = get_lock_remaining(username, ip)
            minutes = max(1, (remaining + 59) // 60)  # round up
            messages.error(
                request,
                f'به دلیل تلاش‌های ناموفق مکرر، ورود موقتاً مسدود شده است. '
                f'لطفاً {minutes} دقیقه‌ی دیگر دوباره تلاش کنید.'
            )
            return redirect('accounts:login')

        # ─── ۲. اجرای مسیر استاندارد LoginView ───
        response = super().post(request, *args, **kwargs)

        # ─── ۳. تحلیل نتیجه ───
        # موفق: HttpResponseRedirect (302)
        # ناموفق: TemplateResponse (200 با form.errors)
        if response.status_code == 302:
            # لاگین موفق → پاک کردن شمارنده‌ها
            clear_failures(username, ip)
        else:
            # لاگین ناموفق → ثبت
            locked_layer = register_failure(username, ip)
            if locked_layer:
                messages.error(
                    request,
                    'به دلیل تلاش‌های ناموفق مکرر، ورود موقتاً مسدود شد.'
                )

        return response