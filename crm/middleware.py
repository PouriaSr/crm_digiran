"""
Thread-local برای نگه‌داشتن request و user جاری در signalها.
+ Middleware برای تبدیل خودکار اعداد به فارسی در کل سیستم.
"""
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


class PersianDigitsHTMLParser(HTMLParser):
    """
    پارسر HTML برای تبدیل اعداد به فارسی.
    تگ‌های script، style و textarea را نادیده می‌گیرد و به Attributes (مثل کلاس‌ها) کاری ندارد.
    """

    def __init__(self):
        super().__init__()
        self.result = []
        self.ignore_depth = 0

    def handle_starttag(self, tag, attrs):
        # استفاده از متن اصلی تگ برای جلوگیری از خراب شدن استایل‌ها و لینک‌ها
        self.result.append(self.get_starttag_text())
        if tag in ('script', 'style', 'textarea'):
            self.ignore_depth += 1

    def handle_startendtag(self, tag, attrs):
        self.result.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'textarea'):
            self.ignore_depth = max(0, self.ignore_depth - 1)
        self.result.append(f'</{tag}>')

    def handle_data(self, data):
        if self.ignore_depth > 0:
            self.result.append(data)
        else:
            # فقط متن‌های قابل مشاهده را ترجمه کن
            self.result.append(data.translate(PERSIAN_DIGITS))

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
    مقادیر داخل input ها، کدهای JS و CSS را دست نمی‌زند.
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

        # به‌روزرسانی محتوای پاسخ
        response.content = parser.get_html().encode('utf-8')
        return response