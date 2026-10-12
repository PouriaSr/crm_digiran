import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm.settings')

import django
django.setup()

from django.conf import settings
from django.test import Client
from django.test.utils import CaptureQueriesContext, override_settings
from django.db import connection
from django.contrib.auth import get_user_model
from django.urls import reverse


User = get_user_model()
u = User.objects.filter(is_superuser=True).first()
if u is None:
    print('⚠️ superuser نیست')
    sys.exit(1)

print(f'👤 کاربر: {u.username}')
print(f'⚙️  DEBUG={settings.DEBUG} | ALLOWED_HOSTS={settings.ALLOWED_HOSTS}')
print('─' * 70)

client = Client()
client.force_login(u)


def measure(label, url):
    with CaptureQueriesContext(connection) as ctx:
        try:
            r = client.get(url)
            status = r.status_code
        except Exception as e:
            status = f'ERR: {type(e).__name__}: {e}'
    print(f'{label:30s} | queries={len(ctx.captured_queries):4d} | status={status}')


# ═══ اضافه کردن testserver به ALLOWED_HOSTS برای این اسکریپت ═══
with override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1']):
    try:
        measure('dashboard home', reverse('dashboard:home'))
    except Exception as e:
        print(f'dashboard skip: {e}')

    try:
        measure('attendance report', reverse('hr:attendance_report'))
    except Exception as e:
        print(f'attendance skip: {e}')

    from products.models import Product
    p = Product.all_objects.first()
    if p:
        try:
            measure('product detail', reverse('products:detail', args=[p.pk]))
        except Exception as e:
            print(f'product detail skip: {e}')

    try:
        measure('product list', reverse('products:list'))
    except Exception as e:
        print(f'product list skip: {e}')

print('─' * 70)
