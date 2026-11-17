"""Message rendering and narrowly-scoped provider connection checks."""
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from django.core.exceptions import ValidationError
from django.utils import timezone

VARIABLES = {
    'customer_name': 'نام مخاطب', 'customer_mobile': 'شماره مخاطب',
    'company_name': 'نام مجموعه', 'expert_name': 'نام کارشناس',
    'task_title': 'عنوان پیگیری', 'contract_number': 'شماره قرارداد',
    'amount': 'مبلغ', 'due_date': 'سررسید', 'address': 'آدرس',
    'date': 'تاریخ امروز', 'time': 'ساعت',
}
DEFAULT_TEMPLATE = 'سلام {customer_name}،\nیادآوری {task_title} از طرف {company_name}.\nزمان: {date} ساعت {time}'
PROVIDERS = {
    'sms': [('pending', 'هنوز انتخاب نشده'), ('kavenegar', 'کاوه‌نگار'), ('melipayamak', 'ملی پیامک — ارسال ساده'), ('faraz', 'فراز اس‌ام‌اس'), ('custom', 'سرویس دیگر')],
    'email': [('pending', 'هنوز انتخاب نشده'), ('smtp', 'SMTP'), ('custom', 'سرویس ایمیل API')],
    'whatsapp': [('pending', 'هنوز انتخاب نشده'), ('meta', 'WhatsApp Business / Meta'), ('custom', 'ارائه‌دهنده دیگر')],
}

MELLIPAYAMAK_SIMPLE_HOST = 'console.melipayamak.com'
MELLIPAYAMAK_SIMPLE_ENV = 'MELLIPAYAMAK_SIMPLE_API_URL'


class ProviderConnectionError(Exception):
    """A safe, user-facing connection failure without credentials or raw response bodies."""


def _melipayamak_simple_url(config):
    """Read and strictly validate the private simple-send URL without exposing it."""
    if config.provider != 'melipayamak':
        raise ProviderConnectionError('سرویس انتخاب‌شده ملی‌پیامک نیست.')
    env_name = (config.credential_env or '').strip()
    endpoint = os.environ.get(env_name, '').strip() if env_name else ''
    if not endpoint:
        raise ProviderConnectionError('نشانی محرمانه API در متغیر محیطی هاست تنظیم نشده است.')
    parsed = urlsplit(endpoint)
    if (parsed.scheme != 'https' or parsed.hostname != MELLIPAYAMAK_SIMPLE_HOST or parsed.port is not None or
            parsed.username or parsed.password or parsed.query or parsed.fragment or
            not re.fullmatch(r'/api/send/simple/[A-Za-z0-9_-]{16,200}', parsed.path)):
        raise ProviderConnectionError('مقدار متغیر محیطی، نشانی معتبر «ارسال ساده» ملی‌پیامک نیست.')
    return endpoint


def verify_melipayamak(config, timeout=10):
    """Validate the simple-send configuration locally; it intentionally sends nothing."""
    del timeout
    _melipayamak_simple_url(config)
    if not config.sender.strip():
        raise ProviderConnectionError('خط فرستنده تنظیم نشده است.')
    return True


def send_melipayamak(config, recipient, text, timeout=15):
    """Send one real SMS through MelliPayamak's private simple-send JSON endpoint."""
    endpoint = _melipayamak_simple_url(config)
    if not config.sender.strip():
        raise ProviderConnectionError('خط فرستنده تنظیم نشده است.')
    request = Request(
        endpoint,
        data=json.dumps({'from': config.sender.strip(), 'to': recipient, 'text': text}, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json; charset=utf-8', 'Accept': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read(65536).decode('utf-8'))
    except HTTPError as error:
        raise ProviderConnectionError(f'ملی‌پیامک درخواست را نپذیرفت (HTTP {error.code})؛ خط فرستنده و وضعیت سرویس را بررسی کنید.')
    except (URLError, TimeoutError, OSError, UnicodeError, json.JSONDecodeError):
        raise ProviderConnectionError('پاسخ معتبر از ملی‌پیامک دریافت نشد؛ شبکه و وضعیت سرویس را بررسی کنید.')
    try:
        reference = str(payload.get('recId') or '').strip()
        provider_status = re.sub(r'\s+', ' ', str(payload.get('status') or '')).strip()
    except (AttributeError, TypeError, ValueError):
        raise ProviderConnectionError('ساختار پاسخ ملی‌پیامک معتبر نبود.')
    if not reference or not reference.isascii() or not reference.isdigit() or int(reference) <= 0:
        # Provider status is useful for support, but never show URLs or an unbounded response.
        provider_status = re.sub(r'https?://\S+', '[نشانی حذف شد]', provider_status)[:240]
        detail = f' پیام سرویس: {provider_status}' if provider_status else ''
        raise ProviderConnectionError(
            'ملی‌پیامک شناسه معتبر ارسال برنگرداند؛ خط فرستنده، گیرنده و متن را بررسی کنید.' + detail
        )
    return reference


def validate_template(value):
    # Do not evaluate Django templates, Python format expressions or attributes.
    remainder = re.sub(r'\{(' + '|'.join(VARIABLES) + r')\}', '', value)
    if '{' in remainder or '}' in remainder:
        raise ValidationError('فقط متغیرهای معرفی‌شده را با یک جفت آکولاد وارد کنید؛ مانند {customer_name}.')
    return value


def render_message(template, values):
    validate_template(template)
    return re.sub(r'\{(' + '|'.join(VARIABLES) + r')\}', lambda m: values.get(m.group(1), ''), template)


def sample_values(cleaned):
    now = timezone.localtime()
    from dashboard.templatetags.fa_numbers import jdate
    return {
        'customer_name': cleaned['sample_name'], 'customer_mobile': cleaned['recipient'],
        'company_name': cleaned['company_name'], 'expert_name': 'کارشناس دیجیران',
        'task_title': cleaned['task_title'], 'contract_number': 'DG-1405-0001',
        'amount': '۱٬۰۰۰٬۰۰۰ تومان', 'due_date': jdate(now, 'Y/m/d'),
        'address': cleaned['sample_address'], 'date': jdate(now, 'Y/m/d'), 'time': now.strftime('%H:%M'),
    }


def configuration_gaps(config):
    missing = []
    if config.provider in ('', 'pending'):
        missing.append('انتخاب سرویس')
    if not config.sender:
        missing.append('فرستنده / داخلی')
    if not config.credential_env:
        missing.append('نام متغیر اعتبار اتصال')
    sms_required = [] if config.provider == 'melipayamak' else ['endpoint']
    required = {'sms': sms_required, 'email': ['endpoint'] if config.provider == 'custom' else ['host', 'port'], 'whatsapp': ['endpoint', 'account_id']}
    labels = {'endpoint': 'نشانی API', 'username_env': 'نام متغیر نام کاربری', 'host': 'میزبان', 'port': 'پورت', 'account_id': 'شناسه حساب تجاری'}
    for key in required[config.channel]:
        if not config.connection.get(key):
            missing.append(labels[key])
    if config.channel == 'sms' and config.provider == 'melipayamak' and config.credential_env:
        if not os.environ.get(config.credential_env, '').strip():
            missing.append('مقدار متغیر محیطی نشانی محرمانه API')
    return missing
