"""
Thread-local برای نگه‌داشتن کاربر جاری در signalها.
اجازه می‌دهد signalها بدون دسترسی مستقیم به request،
نویسنده‌ی تغییرات را ثبت کنند (۷.۹ و ۸.۴).
"""
import threading


_thread_locals = threading.local()


def get_current_user():
    """کاربر جاری درخواست HTTP — یا None اگر خارج از request باشه"""
    return getattr(_thread_locals, 'user', None)


class CurrentUserMiddleware:
    """
    کاربر جاری را در thread-local ذخیره می‌کند.
    باید بعد از AuthenticationMiddleware قرار بگیرد.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.user = getattr(request, 'user', None)
        try:
            response = self.get_response(request)
        finally:
            _thread_locals.user = None
        return response