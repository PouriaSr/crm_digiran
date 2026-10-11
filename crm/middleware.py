"""
Thread-local برای نگه‌داشتن request و user جاری در signalها.
اجازه می‌دهد signalها بدون دسترسی مستقیم به request،
نویسنده و IP تغییرات را ثبت کنند (۷.۹ و ۸.۴).
"""
import threading


_thread_locals = threading.local()


def get_current_user():
    """کاربر جاری درخواست HTTP — یا None اگر خارج از request باشه"""
    return getattr(_thread_locals, 'user', None)


def get_current_request():
    """request جاری — یا None اگه خارج از HTTP باشه"""
    return getattr(_thread_locals, 'request', None)


class CurrentUserMiddleware:
    """
    کاربر و request جاری را در thread-local ذخیره می‌کند.
    باید بعد از AuthenticationMiddleware قرار بگیرد.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.request = request
        _thread_locals.user = getattr(request, 'user', None)
        try:
            response = self.get_response(request)
        finally:
            _thread_locals.request = None
            _thread_locals.user = None
        return response