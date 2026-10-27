"""
Django settings for crm project — CRM Digiran
پشتیبانی از محیط توسعه و تولید به‌صورت env-driven
"""
from pathlib import Path
import os
import urllib.parse

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

# ─── Render: اضافه‌کردن خودکار external hostname ───
RENDER_EXTERNAL_HOSTNAME = os.getenv('RENDER_EXTERNAL_HOSTNAME', '').strip()
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    if o.strip()
]

# ─── Render: اضافه‌کردن خودکار trusted origin ───
if RENDER_EXTERNAL_HOSTNAME:
    _render_origin = f'https://{RENDER_EXTERNAL_HOSTNAME}'
    if _render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_render_origin)


# ═══════════════════════════════════════════════════════════
# اپلیکیشن‌ها
# ═══════════════════════════════════════════════════════════
INSTALLED_APPS = [
    # Unfold باید قبل از admin باشه
    'unfold',
    'unfold.contrib.filters',

    # WhiteNoise — قبل از staticfiles
    'whitenoise.runserver_nostatic',

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
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',

    # Local apps
    'accounts',
    'customers',
    'calls',
    'products',
    'sales',
    'hr',
    'dashboard',
    'audit',
    'ads',
]


# ═══════════════════════════════════════════════════════════
# Middleware
# ═══════════════════════════════════════════════════════════
# ⚠️ ترتیب حیاتی است:
#   1. SecurityMiddleware — اول
#   2. WhiteNoiseMiddleware — بلافاصله بعد از Security
#   3. Authentication → CurrentUser → TwoFactor
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',

    # ⚠️ CurrentUserMiddleware باید بعد از AuthenticationMiddleware باشه
    'crm.middleware.CurrentUserMiddleware',
    'crm.middleware.NoStoreForAuthenticatedMiddleware',
    'accounts.twofa_middleware.TwoFactorEnforcementMiddleware',

    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',

    # ⭐ تبدیل خودکار اعداد به فارسی در کل سیستم
    'crm.middleware.PersianDigitsMiddleware',
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
# ترتیب اولویت:
#   1. DATABASE_URL (postgres:// یا mysql://)
#   2. DB_ENGINE صریح با DB_* جدا
#   3. SQLite (fallback — فقط برای dev)
DATABASE_URL = os.getenv('DATABASE_URL', '').strip()


def _parse_database_url(url):
    """
    تبدیل DATABASE_URL به کانفیگ Django
    شامل پشتیبانی از query params مثل ?sslmode=require (لازم برای Supabase/Neon)
    """
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()

    # ─── پارس کردن query string (sslmode, etc.) ───
    query_params = urllib.parse.parse_qs(parsed.query)

    if scheme in ('postgres', 'postgresql'):
        options = {}
        if 'sslmode' in query_params:
            options['sslmode'] = query_params['sslmode'][0]

        config = {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': parsed.path.lstrip('/'),
            'USER': urllib.parse.unquote(parsed.username or ''),
            'PASSWORD': urllib.parse.unquote(parsed.password or ''),
            'HOST': parsed.hostname or 'localhost',
            'PORT': str(parsed.port or 5432),
            'CONN_MAX_AGE': 600,
            'CONN_HEALTH_CHECKS': True,
        }
        if options:
            config['OPTIONS'] = options
        return config

    if scheme in ('mysql', 'mysql+pymysql'):
        options = {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        }
        if 'ssl_mode' in query_params:
            options['ssl_mode'] = query_params['ssl_mode'][0]

        return {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': parsed.path.lstrip('/'),
            'USER': urllib.parse.unquote(parsed.username or ''),
            'PASSWORD': urllib.parse.unquote(parsed.password or ''),
            'HOST': parsed.hostname or 'localhost',
            'PORT': str(parsed.port or 3306),
            'OPTIONS': options,
            'CONN_MAX_AGE': 60,
        }

    return None


_parsed_db = _parse_database_url(DATABASE_URL) if DATABASE_URL else None

if _parsed_db:
    DATABASES = {'default': _parsed_db}
elif os.getenv('DB_ENGINE') == 'mysql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.getenv('DB_NAME'),
            'USER': os.getenv('DB_USER'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
            'CONN_MAX_AGE': 60,
        }
    }
else:
    # ─── fallback: SQLite (فقط برای dev لوکال) ───
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# ═══════════════════════════════════════════════════════════
# Cache — برای rate limiting و session caching (۸.۲)
# ═══════════════════════════════════════════════════════════
# نکته: روی Render Free، Redis نداری. LocMemCache استفاده می‌شه.
#       این یعنی rate limiting per-worker کار می‌کنه، نه global.
#       برای production جدی، از Upstash Redis (رایگان) استفاده کن.
REDIS_URL = os.getenv('REDIS_URL', '').strip()

if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
            'KEY_PREFIX': 'crm',
            'TIMEOUT': 300,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'crm-digiran-cache',
            'TIMEOUT': 300,
        }
    }


# ═══════════════════════════════════════════════════════════
# Rate limiting روی login (۸.۲)
# ═══════════════════════════════════════════════════════════
LOGIN_FAILED_ATTEMPTS = int(os.getenv('LOGIN_FAILED_ATTEMPTS', '5'))
LOGIN_FAILED_IP_ATTEMPTS = int(os.getenv('LOGIN_FAILED_IP_ATTEMPTS', '20'))
LOGIN_FAILED_WINDOW = int(os.getenv('LOGIN_FAILED_WINDOW', str(15 * 60)))
LOGIN_LOCKOUT = int(os.getenv('LOGIN_LOCKOUT', str(15 * 60)))


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

# ─── WhiteNoise: فشرده‌سازی خودکار استاتیک‌ها ───
# نکته: CompressedStaticFilesStorage (بدون Manifest) استفاده می‌شه
#       چون Manifest در بعضی setup‌ها با فایل‌های جانبی (مثل تصاویر CSS) مشکل داره
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

WHITENOISE_MAX_AGE = 31536000  # 1 year cache برای استاتیک‌ها
WHITENOISE_AUTOREFRESH = DEBUG  # فقط در dev، در production کش می‌کنه


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
    if SECRET_KEY == 'django-insecure-change-me-in-production':
        raise ValueError(
            'در حالت production، SECRET_KEY باید در .env تنظیم شود. '
            'یک کلید تصادفی بساز: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"'
        )

    # ─── HTTPS ───
    # روی Render، SSL خودکار فعاله — این‌ها باید True باشن
    # اگه لوکال با DEBUG=False تست می‌کنی، توی .env ست کن به False
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True').lower() == 'true'
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'True').lower() == 'true'
    CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE', 'True').lower() == 'true'

    SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'

    # ─── Render: پروکسی SSL ───
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_X_FORWARDED_HOST = True


# ═══════════════════════════════════════════════════════════
# Logging
# ═══════════════════════════════════════════════════════════
LOG_DIR = BASE_DIR / 'logs'

# ساخت پوشه لاگ — با احتیاط چون روی Render فایل‌سیستم ephemeral هست
try:
    LOG_DIR.mkdir(exist_ok=True)
    _log_file = str(LOG_DIR / 'crm.log')
    _handlers_list = ['console', 'file']
except (OSError, PermissionError):
    _log_file = None
    _handlers_list = ['console']


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
    },
    'root': {
        'handlers': _handlers_list,
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': _handlers_list,
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': _handlers_list,
            'level': 'WARNING',
            'propagate': False,
        },
        'django.security': {
            'handlers': _handlers_list,
            'level': 'WARNING',
            'propagate': False,
        },
        'crm.security': {
            'handlers': _handlers_list,
            'level': 'WARNING',
            'propagate': False,
        },
        'crm.ratelimit': {
            'handlers': _handlers_list,
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# اضافه کردن file handler فقط اگه پوشه قابل نوشتن بود
# ⚠️ روی Render، فایل‌سیستم ephemeral هست — لاگ‌ها با هر deploy پاک می‌شن
if _log_file:
    LOGGING['handlers']['file'] = {
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': _log_file,
        'maxBytes': 10 * 1024 * 1024,
        'backupCount': 5,
        'formatter': 'verbose',
    }


# ═══════════════════════════════════════════════════════════
# 2FA — فاز ۸.۳
# ═══════════════════════════════════════════════════════════
TWO_FACTOR_REQUIRED_FOR_SUPERUSER = os.getenv(
    'TWO_FACTOR_REQUIRED_FOR_SUPERUSER', 'False'
).lower() in ('true', '1', 'yes')

TWO_FACTOR_RECOVERY_CODES_COUNT = int(os.getenv('TWO_FACTOR_RECOVERY_CODES_COUNT', '10'))