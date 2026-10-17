"""
Passenger WSGI entry point — برای هاست اشتراکی cPanel (میزبان‌فا).

این فایل توسط mod_passenger خونده می‌شه و application رو اجرا می‌کنه.
"""
import os
import sys

# ─── مسیر پروژه رو به sys.path اضافه کن ───
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# ─── تنظیمات Django ───
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm.settings')

# ─── بارگذاری اپلیکیشن WSGI ───
from crm.wsgi import application
