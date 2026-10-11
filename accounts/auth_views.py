"""
Views احراز هویت سفارشی — ۸.۲ + ۸.۳
"""
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect

from django_otp.plugins.otp_totp.models import TOTPDevice

from .ratelimit import (
    get_client_ip,
    is_locked,
    register_failure,
    clear_failures,
    get_lock_remaining,
)


class RateLimitedLoginView(LoginView):
    """
    LoginView با محافظت brute-force + پشتیبانی 2FA.
    """
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        username = request.POST.get('username', '').strip()
        ip = get_client_ip(request)

        # ─── ۱. قفل بودن؟ ───
        if is_locked(username, ip):
            remaining = get_lock_remaining(username, ip)
            minutes = max(1, (remaining + 59) // 60)
            messages.error(
                request,
                f'به دلیل تلاش‌های ناموفق مکرر، ورود موقتاً مسدود شده است. '
                f'لطفاً {minutes} دقیقه‌ی دیگر دوباره تلاش کنید.'
            )
            return redirect('accounts:login')

        # ─── ۲. اجرای LoginView ───
        response = super().post(request, *args, **kwargs)

        # ─── ۳. تحلیل نتیجه ───
        # موفق: 302 — ولی ممکنه 2FA verify باشه
        # ناموفق: 200 با form.errors
        if response.status_code == 302:
            clear_failures(username, ip)
        else:
            locked_layer = register_failure(username, ip)
            if locked_layer:
                messages.error(
                    request,
                    'به دلیل تلاش‌های ناموفق مکرر، ورود موقتاً مسدود شد.'
                )

        return response

    def form_valid(self, form):
        """اگه 2FA فعاله، کاربر رو به verify redirect کن"""
        user = form.get_user()
        device = TOTPDevice.objects.filter(user=user, confirmed=True).first()

        if device:
            # ذخیره در session برای verify
            self.request.session['2fa_user_id'] = user.pk
            self.request.session['2fa_next'] = self.get_success_url()
            return redirect('accounts:twofa_verify')

        # بدون 2FA → مسیر عادی
        return super().form_valid(form)