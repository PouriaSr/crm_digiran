"""
Thread-local برای نگه‌داشتن request و user جاری در signalها.
+ Middleware برای تبدیل خودکار اعداد به فارسی در کل سیستم.
"""
import html
import threading
import re
from html.parser import HTMLParser

from .numerals import PERSIAN_DIGITS, normalize_input, preserve_field, persian_digits


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
class NormalizeNumeralInputsMiddleware:
    """Normalize HTTP form/search values before validators, views and model lookups.

    Keys, files, JSON bodies, credentials and signed values remain untouched.
    QueryDict lists are retained (formsets and multi-selects depend on them).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        for attribute in ('GET', 'POST'):
            original = getattr(request, attribute)
            normalized = original.copy()
            for key, values in original.lists():
                if not preserve_field(key):
                    normalized.setlist(key, [normalize_input(value) for value in values])
            setattr(request, attribute, normalized)
        return self.get_response(request)

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
        self.result.append(self._start_tag(tag, attrs))
        if tag in _RAW_CONTENT_TAGS:
            self._mode_stack.append('raw')
        elif tag in _PRESERVE_DIGITS_TAGS:
            self._mode_stack.append('preserve')

    def handle_startendtag(self, tag, attrs):
        self.result.append(self._start_tag(tag, attrs, closed=True))

    def _start_tag(self, tag, attrs, closed=False):
        display = {'title', 'placeholder', 'aria-label', 'alt'}
        if tag in ('option', 'optgroup'):
            display.add('label')
        if not any(name in display and value is not None and persian_digits(value) != value for name, value in attrs):
            return self.get_starttag_text()
        rendered = []
        for name, value in attrs:
            if value is None:
                rendered.append(' ' + name)
            else:
                if name in display:
                    value = persian_digits(value)
                rendered.append(' ' + name + '="' + html.escape(value, quote=True) + '"')
        return '<' + tag + ''.join(rendered) + ('/>' if closed else '>')

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

        # Also cover standalone/admin pages that do not extend our base. Partial
        # HTMX responses inherit their parent's assets and are not injected.
        if 'id="crm-numeral-inputs"' not in content and re.search(r'</head\s*>', content, flags=re.I):
            from django.template.loader import render_to_string
            assets = render_to_string('includes/_numerals.html')
            content = re.sub(r'</head\s*>', lambda match: assets + match.group(), content, count=1, flags=re.I)

        parser = PersianDigitsHTMLParser()
        parser.feed(content)

        # به‌روزرسانی محتوای محافظت‌شده‌ی پاسخ
        response.content = parser.get_html().encode('utf-8')
        if response.has_header('Content-Length'):
            response['Content-Length'] = str(len(response.content))
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
