"""
Thread-local برای نگه‌داشتن request و user جاری در signalها.
+ Middleware برای تبدیل خودکار اعداد به فارسی در کل سیستم.
"""
import html
import threading
from html.parser import HTMLParser


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


# ═══════════════════════════════════════════════════════════
# تبدیل خودکار اعداد انگلیسی به فارسی در کل سیستم
# ═══════════════════════════════════════════════════════════
PERSIAN_DIGITS = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')

# تگ‌هایی که محتوایشان JavaScript/CSS خام است — هرگز تغییر نمی‌کنند
_RAW_CONTENT_TAGS = ('script', 'style')

# تگ‌هایی که ارقامشان باید انگلیسی بماند (کد بازیابی، توکن، نمونه کد)
# ولی همچنان باید HTML-escape شوند تا XSS نشود
_PRESERVE_DIGITS_TAGS = ('textarea', 'pre', 'code', 'samp', 'kbd')

_ALL_IGNORE_TAGS = _RAW_CONTENT_TAGS + _PRESERVE_DIGITS_TAGS


class PersianDigitsHTMLParser(HTMLParser):
    """
    پارسر HTML برای تبدیل اعداد به فارسی.

    رفتار به تفکیک context:
    - داخل `<script>` / `<style>` → بدون تغییر (JS/CSS باید سالم بماند)
    - داخل `<pre>` / `<code>` / `<textarea>` / `<samp>` / `<kbd>` →
        HTML-escape می‌شود ولی ارقام انگلیسی حفظ می‌شوند
        (برای کد بازیابی، API key، نمونه کد)
    - متن عادی → HTML-escape + تبدیل ارقام به فارسی

    ⚠️ نکته امنیتی مهم:
    HTMLParser با convert_charrefs=True (پیش‌فرض) مقدار entity‌ها را
    دیکد می‌کند (مثلاً `&lt;` → `<`). پس اگر خروجی handle_data را بدون
    escape به HTML برگردانیم، Django escaping بی‌اثر می‌شود و XSS رخ
    می‌دهد. به همین دلیل خروجی همه‌ی حالت‌ها (به‌جز raw) با
    html.escape دوباره امن می‌شود.
    """

    def __init__(self):
        super().__init__()
        self.result = []
        self._mode_stack = []  # 'raw' یا 'preserve'

    def handle_starttag(self, tag, attrs):
        # استفاده از متن اصلی تگ برای جلوگیری از خراب شدن استایل‌ها و لینک‌ها
        self.result.append(self.get_starttag_text())
        if tag in _RAW_CONTENT_TAGS:
            self._mode_stack.append('raw')
        elif tag in _PRESERVE_DIGITS_TAGS:
            self._mode_stack.append('preserve')

    def handle_startendtag(self, tag, attrs):
        self.result.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if tag in _ALL_IGNORE_TAGS and self._mode_stack:
            self._mode_stack.pop()
        self.result.append(f'</{tag}>')

    def handle_data(self, data):
        mode = self._mode_stack[-1] if self._mode_stack else None

        if mode == 'raw':
            # داخل script/style — دست‌نخورده (JS/CSS)
            self.result.append(data)
        elif mode == 'preserve':
            # داخل pre/code/... — escape بدون ترجمه ارقام
            self.result.append(html.escape(data, quote=False))
        else:
            # متن معمولی — escape + ترجمه ارقام
            translated = data.translate(PERSIAN_DIGITS)
            self.result.append(html.escape(translated, quote=False))

    def handle_decl(self, decl):
        self.result.append(f'<!{decl}>')

    def handle_comment(self, data):
        self.result.append(f'<!--{data}-->')

    def handle_entityref(self, name):
        self.result.append(f'&{name};')

    def handle_charref(self, name):
        self.result.append(f'&#{name};')

    def get_html(self):
        return ''.join(self.result)


class PersianDigitsMiddleware:
    """
    تمام اعداد انگلیسی موجود در خروجی HTML را به فارسی تبدیل می‌کند.
    مقادیر داخل input ها، کدهای JS و CSS، و تگ‌های code/pre دست نمی‌خورند.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # فقط پاسخ‌های HTML را پردازش کن (JSON ها، فایل‌ها و Streaming ها دست نخورده می‌مانند)
        if getattr(response, 'streaming', False):
            return response

        if not response.get('Content-Type', '').startswith('text/html'):
            return response

        try:
            content = response.content.decode('utf-8')
        except UnicodeDecodeError:
            return response

        parser = PersianDigitsHTMLParser()
        parser.feed(content)

        # به‌روزرسانی محتوای محافظت‌شده‌ی پاسخ
        response.content = parser.get_html().encode('utf-8')
        return response


# ═══════════════════════════════════════════════════════════
# بدون کش برای کاربران واردشده — دسترسی‌ها همین لحظه اعمال شوند
# ═══════════════════════════════════════════════════════════
class NoStoreForAuthenticatedMiddleware:
    """
    پاسخ‌های HTML کاربران واردشده با no-store فرستاده می‌شوند تا:
      • پس از «انتقال مشتری» یا تغییر سطح دسترسی، صفحه‌ی قدیمی از کش میانی/مرورگر
        نمایش داده نشود و کاربر مجبور به رفرش دستی نباشد.
      • دکمه‌ی Back مرورگر (bfcache) نسخه‌ی قدیمی را نشان ندهد.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return response

        content_type = (response.get('Content-Type') or '').lower()
        if 'text/html' not in content_type:
            return response

        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        response['Vary'] = 'Cookie'
        return response
