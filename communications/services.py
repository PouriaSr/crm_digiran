"""Message rendering and narrowly-scoped provider connection checks."""
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from django.core.exceptions import ValidationError
from django.utils import timezone

VARIABLES = {'customer_name': 'نام مخاطب', 'company_name': 'نام مجموعه', 'task_title': 'عنوان پیگیری', 'date': 'تاریخ', 'time': 'ساعت'}
DEFAULT_TEMPLATE = 'سلام {customer_name}،\nیادآوری {task_title} از طرف {company_name}.\nزمان: {date} ساعت {time}'
PROVIDERS = {
    'sms': [('pending', 'هنوز انتخاب نشده'), ('kavenegar', 'کاوه‌نگار'), ('melipayamak', 'ملی پیامک'), ('faraz', 'فراز اس‌ام‌اس'), ('custom', 'سرویس دیگر')],
    'email': [('pending', 'هنوز انتخاب نشده'), ('smtp', 'SMTP'), ('custom', 'سرویس ایمیل API')],
    'whatsapp': [('pending', 'هنوز انتخاب نشده'), ('meta', 'WhatsApp Business / Meta'), ('custom', 'ارائه‌دهنده دیگر')],
}

MELLIPAYAMAK_SEND_URL = 'https://rest.payamak-panel.com/api/SendSMS/SendSMS'
MELLIPAYAMAK_CREDIT_URL = 'https://rest.payamak-panel.com/api/SendSMS/GetCredit'


class ProviderConnectionError(Exception):
    """A safe, user-facing connection failure without credentials or raw response bodies."""


def verify_melipayamak(config, timeout=10):
    """Verify credentials by reading credit; this never sends an SMS."""
    if config.provider != 'melipayamak':
        raise ProviderConnectionError('سرویس انتخاب‌شده ملی‌پیامک نیست.')
    if config.connection.get('endpoint') != MELLIPAYAMAK_SEND_URL:
        raise ProviderConnectionError('نشانی API ملی‌پیامک با مستند رسمی مطابقت ندارد.')
    username_env = config.connection.get('username_env', '')
    api_key_env = config.credential_env
    username = os.environ.get(username_env, '').strip() if username_env else ''
    api_key = os.environ.get(api_key_env, '').strip() if api_key_env else ''
    if not username or not api_key:
        raise ProviderConnectionError('نام کاربری یا کلید API در متغیرهای محیطی هاست تنظیم نشده است.')
    request = Request(
        MELLIPAYAMAK_CREDIT_URL,
        data=urlencode({'username': username, 'password': api_key}).encode('utf-8'),
        headers={'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read(65536).decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError, json.JSONDecodeError):
        raise ProviderConnectionError('پاسخ معتبر از ملی‌پیامک دریافت نشد؛ دسترسی شبکه، IP مجاز و مشخصات اتصال را بررسی کنید.')
    try:
        status = int(payload.get('RetStatus'))
    except (AttributeError, TypeError, ValueError):
        raise ProviderConnectionError('ساختار پاسخ ملی‌پیامک معتبر نبود.')
    if status != 1:
        errors = {
            -111: 'IP درخواست‌کننده معتبر نیست.', -110: 'باید API Key به‌جای رمز عبور استفاده شود.',
            -109: 'IP خروجی هاست در فهرست IPهای مجاز API ثبت نشده است.',
            -108: 'IP به‌دلیل تلاش ناموفق مسدود شده است.', 0: 'نام کاربری یا API Key صحیح نیست.',
        }
        raise ProviderConnectionError(errors.get(status, f'ملی‌پیامک درخواست را نپذیرفت (کد {status}).'))
    return payload.get('Value')


def send_melipayamak(config, recipient, text, timeout=15):
    """Send one real SMS through the documented MelliPayamak REST endpoint."""
    if config.provider != 'melipayamak' or config.connection.get('endpoint') != MELLIPAYAMAK_SEND_URL:
        raise ProviderConnectionError('پیکربندی رسمی ملی‌پیامک انتخاب نشده است.')
    username_env = config.connection.get('username_env', '')
    username = os.environ.get(username_env, '').strip() if username_env else ''
    api_key = os.environ.get(config.credential_env, '').strip() if config.credential_env else ''
    if not username or not api_key:
        raise ProviderConnectionError('نام کاربری یا کلید API در متغیرهای محیطی هاست تنظیم نشده است.')
    if not config.sender.strip():
        raise ProviderConnectionError('خط فرستنده تنظیم نشده است.')
    request = Request(
        MELLIPAYAMAK_SEND_URL,
        data=urlencode({
            'username': username, 'password': api_key, 'to': recipient,
            'from': config.sender.strip(), 'text': text, 'isFlash': 'false',
        }).encode('utf-8'),
        headers={'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read(65536).decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError, json.JSONDecodeError):
        raise ProviderConnectionError('پاسخ معتبر از ملی‌پیامک دریافت نشد؛ شبکه، IP مجاز و وضعیت سرویس را بررسی کنید.')
    try:
        status = int(payload.get('RetStatus'))
    except (AttributeError, TypeError, ValueError):
        raise ProviderConnectionError('ساختار پاسخ ملی‌پیامک معتبر نبود.')
    if status != 1:
        errors = {
            -111: 'IP درخواست‌کننده معتبر نیست.', -110: 'باید API Key به‌جای رمز عبور استفاده شود.',
            -109: 'IP خروجی هاست در فهرست IPهای مجاز API ثبت نشده است.',
            -108: 'IP به‌دلیل تلاش ناموفق مسدود شده است.', 0: 'نام کاربری یا API Key صحیح نیست.',
            2: 'اعتبار پیامکی کافی نیست.', 3: 'محدودیت ارسال روزانه فعال است.',
            4: 'حجم ارسال از محدودیت عبور کرده است.', 5: 'شماره فرستنده معتبر نیست.',
            7: 'متن شامل واژه فیلترشده است.', 11: 'پیامک ارسال نشد.', 14: 'متن شامل لینک غیرمجاز است.',
            16: 'گیرنده‌ای پیدا نشد.', 17: 'متن پیامک خالی است.', 18: 'شماره گیرنده معتبر نیست.',
        }
        raise ProviderConnectionError(errors.get(status, f'ملی‌پیامک ارسال را نپذیرفت (کد {status}).'))
    reference = str(payload.get('Value') or '').strip()
    if not reference or reference == '11':
        raise ProviderConnectionError('ملی‌پیامک شناسه معتبر ارسال برنگرداند.')
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
    return {'customer_name': cleaned['sample_name'], 'company_name': cleaned['company_name'],
            'task_title': cleaned['task_title'], 'date': jdate(now, 'Y/m/d'), 'time': now.strftime('%H:%M')}


def configuration_gaps(config):
    missing = []
    if config.provider in ('', 'pending'):
        missing.append('انتخاب سرویس')
    if not config.sender:
        missing.append('فرستنده / داخلی')
    if not config.credential_env:
        missing.append('نام متغیر اعتبار اتصال')
    sms_required = ['endpoint', 'username_env'] if config.provider == 'melipayamak' else ['endpoint']
    required = {'sms': sms_required, 'email': ['endpoint'] if config.provider == 'custom' else ['host', 'port'], 'whatsapp': ['endpoint', 'account_id']}
    labels = {'endpoint': 'نشانی API', 'username_env': 'نام متغیر نام کاربری', 'host': 'میزبان', 'port': 'پورت', 'account_id': 'شناسه حساب تجاری'}
    for key in required[config.channel]:
        if not config.connection.get(key):
            missing.append(labels[key])
    return missing
