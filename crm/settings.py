"""
Django settings for crm project — CRM Digiran
پشتیبانی از محیط توسعه و تولید به‌صورت env-driven
"""
from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════
# مسیرها
# ═══════════════════════════════════════════════════════════
BASE_DIR = Path(__file__).resolve().parent.parent


# ═══════════════════════════════════════════════════════════
# امنیت پایه
# ═══════════════════════════════════════════════════════════
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-me-in-production')

DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')
    if h.strip()
]

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    if o.strip()
]


# ═══════════════════════════════════════════════════════════
# اپلیکیشن‌ها
# ═══════════════════════════════════════════════════════════
INSTALLED_APPS = [
    # Unfold باید قبل از admin باشه
    'unfold',
    'unfold.contrib.filters',

    # Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'django_htmx',
    'widget_tweaks',

    # Local apps
    'accounts',
    'customers',
    'calls',
    'products',
    'sales',
    'hr',
    'dashboard',
]


# ═══════════════════════════════════════════════════════════
# Middleware
# ═══════════════════════════════════════════════════════════
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]


# ═══════════════════════════════════════════════════════════
# URL و WSGI
# ═══════════════════════════════════════════════════════════
ROOT_URLCONF = 'crm.urls'
WSGI_APPLICATION = 'crm.wsgi.application'


# ═══════════════════════════════════════════════════════════
# Templates
# ═══════════════════════════════════════════════════════════
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.permissions_context',
            ],
        },
    },
]


# ═══════════════════════════════════════════════════════════
# دیتابیس
# ═══════════════════════════════════════════════════════════
# در صورت وجود DATABASE_URL از PostgreSQL استفاده می‌کنه،
# وگرنه به SQLite برمی‌گرده (محیط توسعه)
DATABASE_URL = os.getenv('DATABASE_URL', '').strip()

if DATABASE_URL and DATABASE_URL.startswith('postgres'):
    # فرمت: postgres://USER:PASSWORD@HOST:PORT/NAME
    import urllib.parse
    url = urllib.parse.urlparse(DATABASE_URL)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': url.path.lstrip('/'),
            'USER': url.username,
            'PASSWORD': url.password,
            'HOST': url.hostname,
            'PORT': url.port or '5432',
            'CONN_MAX_AGE': 600,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# ═══════════════════════════════════════════════════════════
# اعتبارسنجی رمز
# ═══════════════════════════════════════════════════════════
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 6}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ═══════════════════════════════════════════════════════════
# بین‌المللی‌سازی
# ═══════════════════════════════════════════════════════════
LANGUAGE_CODE = 'fa'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_TZ = True


# ═══════════════════════════════════════════════════════════
# فایل‌های استاتیک و مدیا
# ═══════════════════════════════════════════════════════════
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ═══════════════════════════════════════════════════════════
# پیش‌فرض‌ها
# ═══════════════════════════════════════════════════════════
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ═══════════════════════════════════════════════════════════
# ورود و خروج
# ═══════════════════════════════════════════════════════════
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'dashboard:home'
LOGOUT_REDIRECT_URL = 'accounts:login'


# ═══════════════════════════════════════════════════════════
# اطلاعات شرکت (برای فاکتور چاپی)
# ═══════════════════════════════════════════════════════════
COMPANY_INFO = {
    'name': 'شرکت دیجیران',
    'slogan': 'ارائه‌دهنده خدمات CRM و مدیریت مشتریان',
    'address': 'تهران، خیابان ولیعصر، پلاک ۱۲۳، طبقه ۴',
    'phone': '۰۲۱-۱۲۳۴۵۶۷۸',
    'mobile': '۰۹۱۲۱۲۳۴۵۶۷',
    'email': 'info@digiran.com',
    'website': 'www.digiran.com',
    'national_id': '۱۲۳۴۵۶۷۸۹۰',
    'economic_code': '۱۲۳۴۵۶۷۸۹۰۱۲',
    'postal_code': '۱۲۳۴۵۶۷۸۹۰',
    'logo_path': 'images/logo.gif',
    'bank_info': {
        'bank_name': 'بانک ملت',
        'account_number': '۱۲۳۴۵۶۷۸۹۰',
        'card_number': '۶۱۰۴-۳۳۷۹-۱۲۳۴-۵۶۷۸',
        'iban': 'IR۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹۰۱۲',
        'account_holder': 'شرکت دیجیران',
    },
}


# ═══════════════════════════════════════════════════════════
# تنظیمات امنیتی Production (فقط وقتی DEBUG=False)
# ═══════════════════════════════════════════════════════════
if not DEBUG:
    # ─── اجباری: SECRET_KEY نباید پیش‌فرض باشه ───
    if SECRET_KEY == 'django-insecure-change-me-in-production':
        raise ValueError(
            'در حالت production، SECRET_KEY باید در .env تنظیم شود. '
            'یک کلید تصادفی بساز: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"'
        )

    # ─── HTTPS ───
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True').lower() == 'true'
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # ─── HSTS ───
    SECURE_HSTS_SECONDS = 31536000  # 1 سال
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # ─── سایر ───
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'

    # ─── پروکسی ───
    # اگه پشت Nginx هستی، این‌ها لازمه
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_X_FORWARDED_HOST = True


# ═══════════════════════════════════════════════════════════
# Logging
# ═══════════════════════════════════════════════════════════
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'crm.log',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}