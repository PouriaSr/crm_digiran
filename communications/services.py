"""Local previews only. No provider adapter or outbound transport is enabled."""
import re
from django.core.exceptions import ValidationError
from django.utils import timezone

VARIABLES = {'customer_name': 'نام مخاطب', 'company_name': 'نام مجموعه', 'task_title': 'عنوان پیگیری', 'date': 'تاریخ', 'time': 'ساعت'}
DEFAULT_TEMPLATE = 'سلام {customer_name}،\nیادآوری {task_title} از طرف {company_name}.\nزمان: {date} ساعت {time}'
PROVIDERS = {
    'sms': [('pending', 'هنوز انتخاب نشده'), ('kavenegar', 'کاوه‌نگار'), ('melipayamak', 'ملی پیامک'), ('faraz', 'فراز اس‌ام‌اس'), ('custom', 'سرویس دیگر')],
    'email': [('pending', 'هنوز انتخاب نشده'), ('smtp', 'SMTP'), ('custom', 'سرویس ایمیل API')],
    'whatsapp': [('pending', 'هنوز انتخاب نشده'), ('meta', 'WhatsApp Business / Meta'), ('custom', 'ارائه‌دهنده دیگر')],
    'voip': [('pending', 'هنوز انتخاب نشده'), ('asterisk', 'Asterisk / Issabel'), ('3cx', '3CX'), ('custom', 'مرکز تلفن دیگر')],
}


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
    required = {'sms': ['endpoint'], 'email': ['endpoint'] if config.provider == 'custom' else ['host', 'port'], 'whatsapp': ['endpoint', 'account_id'], 'voip': ['host', 'port']}
    if config.channel == 'voip' and config.connection.get('transport', 'pending') == 'pending':
        missing.append('روش ارتباط با مرکز تلفن')
    labels = {'endpoint': 'نشانی API', 'host': 'میزبان', 'port': 'پورت', 'account_id': 'شناسه حساب تجاری'}
    for key in required[config.channel]:
        if not config.connection.get(key):
            missing.append(labels[key])
    return missing
