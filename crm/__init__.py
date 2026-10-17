"""
crm/__init__.py

Barگذاری .env قبل از settings.py + monkey-patch برای PyMySQL.

توجه: این فایل قبل از settings.py اجرا می‌شه، پس نمیشه از
django.conf.settings استفاده کرد. مستقیم از os.environ می‌خونیم.
"""
import os

from dotenv import load_dotenv

# ─── بارگذاری متغیرهای .env (اگه فایل موجود باشه) ───
load_dotenv()

# ─── Monkey-patch: PyMySQL جایگزین mysqlclient ───
# فقط اگه DB_ENGINE=mysql باشه فعال می‌شه.
# روی هاست اشتراکی cPanel که نمی‌شه mysqlclient (نیاز به کامپایل C) نصب کرد،
# PyMySQL با این ترفند جایگزین می‌شه.
if os.getenv('DB_ENGINE', 'sqlite').lower() == 'mysql':
    import pymysql

    # فریب دادن Django که فکر کنه mysqlclient نسخه 2.2.1 نصبه
    pymysql.version_info = (2, 2, 1, "final", 0)
    pymysql.__version__ = "2.2.1"

    pymysql.install_as_MySQLdb()
