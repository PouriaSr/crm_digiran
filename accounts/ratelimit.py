"""
Rate limiting برای صفحه‌ی ورود — ۸.۲

دو لایه محافظت:
1. per (username + IP):  پس از ۵ تلاش ناموفق، ۱۵ دقیقه قفل
2. per IP:               پس از ۲۰ تلاش ناموفق، ۱۵ دقیقه قفل

از cache بومی Django استفاده می‌کنه — بدون وابستگی خارجی.
"""
import time

from django.conf import settings
from django.core.cache import cache


# ═══════════════════════════════════════════════════════════
# پیش‌فرض‌ها (قابل override از settings)
# ═══════════════════════════════════════════════════════════
_DEFAULT_USER_LIMIT = 5           # حداکثر تلاش ناموفق per (username+IP)
_DEFAULT_IP_LIMIT = 20            # حداکثر تلاش ناموفق per IP
_DEFAULT_WINDOW = 15 * 60         # پنجره‌ی زمانی (ثانیه)
_DEFAULT_LOCKOUT = 15 * 60        # مدت قفل (ثانیه)


def _cfg(name, default):
    return getattr(settings, name, default)


# ═══════════════════════════════════════════════════════════
# کلیدهای cache
# ═══════════════════════════════════════════════════════════
def _key_user(username, ip):
    return f'rl:login:user:{username.lower()}:{ip}'


def _key_ip(ip):
    return f'rl:login:ip:{ip}'


def _lock_user(username, ip):
    return f'rl:login:lock:user:{username.lower()}:{ip}'


def _lock_ip(ip):
    return f'rl:login:lock:ip:{ip}'


# ═══════════════════════════════════════════════════════════
# ابزارها
# ═══════════════════════════════════════════════════════════
def get_client_ip(request):
    """
    IP کاربر با پشتیبانی از پروکسی/load balancer.
    ترتیب اولویت: X-Forwarded-For → X-Real-IP → REMOTE_ADDR
    """
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        # اولین IP در لیست، IP کاربر واقعیه
        return xff.split(',')[0].strip()

    real_ip = request.META.get('HTTP_X_REAL_IP')
    if real_ip:
        return real_ip.strip()

    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def _bump(counter_key, window):
    """
    افزایش شمارنده به‌صورت اتمیک.
    اگه کلید نبود، با مقدار ۱ و TTL=window ست می‌شه.
    """
    if cache.add(counter_key, 1, window):
        return 1
    try:
        return cache.incr(counter_key)
    except ValueError:
        # کلید در فاصله‌ی بین add و incr منقضی شد
        cache.set(counter_key, 1, window)
        return 1


def _set_lock(lock_key, lockout):
    """ذخیره‌ی lock با timestamp انقضا (برای محاسبه‌ی remaining)"""
    expires_at = time.time() + lockout
    cache.set(lock_key, expires_at, lockout)


def _remaining(lock_key):
    """چند ثانیه تا رفع قفل مونده؟ (0 = قفل نیست)"""
    expires_at = cache.get(lock_key)
    if not expires_at:
        return 0
    return max(0, int(expires_at - time.time()))


# ═══════════════════════════════════════════════════════════
# API عمومی
# ═══════════════════════════════════════════════════════════
def is_locked(username, ip):
    """آیا (username, ip) قفل هست؟"""
    return bool(
        cache.get(_lock_user(username, ip))
        or cache.get(_lock_ip(ip))
    )


def get_lock_remaining(username, ip):
    """چند ثانیه تا رفع قفل؟ (0 = قفل نیست)"""
    return max(
        _remaining(_lock_user(username, ip)),
        _remaining(_lock_ip(ip)),
    )


def register_failure(username, ip):
    """
    ثبت یک تلاش ناموفق.
    برمی‌گردونه: 'user' یا 'ip' (کدوم لایه قفل شد) یا None.
    """
    user_limit = _cfg('LOGIN_FAILED_ATTEMPTS', _DEFAULT_USER_LIMIT)
    ip_limit = _cfg('LOGIN_FAILED_IP_ATTEMPTS', _DEFAULT_IP_LIMIT)
    window = _cfg('LOGIN_FAILED_WINDOW', _DEFAULT_WINDOW)
    lockout = _cfg('LOGIN_LOCKOUT', _DEFAULT_LOCKOUT)

    # ─── لایه ۱: per (username+IP) ───
    if username:
        count = _bump(_key_user(username, ip), window)
        if count >= user_limit:
            _set_lock(_lock_user(username, ip), lockout)
            return 'user'

    # ─── لایه ۲: per IP ───
    count_ip = _bump(_key_ip(ip), window)
    if count_ip >= ip_limit:
        _set_lock(_lock_ip(ip), lockout)
        return 'ip'

    return None


def clear_failures(username, ip):
    """پاک کردن همه‌ی شمارنده‌ها پس از لاگین موفق"""
    cache.delete_many([
        _key_user(username, ip),
        _key_ip(ip),
        _lock_user(username, ip),
        _lock_ip(ip),
    ])


def get_remaining_attempts(username, ip):
    """
    تعداد تلاش‌های باقی‌مانده برای این (username, ip).
    None اگه قفل باشه.
    """
    if is_locked(username, ip):
        return None
    limit = _cfg('LOGIN_FAILED_ATTEMPTS', _DEFAULT_USER_LIMIT)
    count = cache.get(_key_user(username, ip), 0)
    return max(0, limit - count)