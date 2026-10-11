"""
Middleware اجبار 2FA برای superuser — فاز ۸.۳

اگه TWO_FACTOR_REQUIRED_FOR_SUPERUSER=True باشه، superuserهایی که 2FA ندارن
به صفحه‌ی setup هدایت می‌شن (به‌جز مسیرهای exempt).
"""
from django.conf import settings
from django.shortcuts import redirect

from django_otp.plugins.otp_totp.models import TOTPDevice


class TwoFactorEnforcementMiddleware:
    EXEMPT_PREFIXES = (
        '/accounts/2fa/',
        '/accounts/logout/',
        '/accounts/login/',
        '/static/',
        '/media/',
        '/admin/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_force_setup(request):
            return redirect('accounts:twofa_setup')
        return self.get_response(request)

    def _should_force_setup(self, request):
        if not getattr(settings, 'TWO_FACTOR_REQUIRED_FOR_SUPERUSER', False):
            return False
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated or not user.is_superuser:
            return False
        # مسیرهای exempt
        for prefix in self.EXEMPT_PREFIXES:
            if request.path.startswith(prefix):
                return False
        # آیا 2FA فعال داره؟
        return not TOTPDevice.objects.filter(user=user, confirmed=True).exists()