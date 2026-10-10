# CRM Digiran

سیستم مدیریت ارتباط با مشتریان و عملیات داخلی کسب‌وکار، توسعه‌یافته با **Python** و **Django**.

هدف پروژه: مدیریت یکپارچه‌ی مشتریان، تماس‌ها، کالاها و انبار، فاکتورها، منابع انسانی و گزارش‌های مدیریتی در یک پنل فارسی و راست‌چین.

---

## فهرست مطالب

- [وضعیت پروژه](#وضعیت-پروژه)
- [فناوری‌ها](#فناوریها)
- [ساختار پروژه](#ساختار-پروژه)
- [راه‌اندازی محیط توسعه](#راهاندازی-محیط-توسعه)
- [نقش‌ها و دسترسی‌ها](#نقشها-و-دسترسیها)
- [قابلیت‌ها](#قابلیتها)
- [نشانی‌های محلی](#نشانیهای-محلی)
- [بکاپ دیتابیس](#بکاپ-دیتابیس)
- [تست‌ها](#تستها)
- [استقرار روی سرور](#استقرار-روی-سرور)
- [نکات امنیتی](#نکات-امنیتی)

---

## وضعیت پروژه

| فاز | عنوان | وضعیت |
|-----|-------|--------|
| ۱ | پاکسازی محیط و وابستگی‌ها | ✅ کامل |
| ۲ | مسائل بحرانی (SET_NULL، StockMovement، RBAC پایه) | ✅ کامل |
| ۳ | هم‌خوانی و باگ‌ها (Signal، تاریخ شمسی، JSON) | ✅ کامل |
| ۴ | RBAC (کنترل دسترسی نقش‌محور) | ✅ کامل |
| ۵ | تست‌ها و آماده‌سازی استقرار | 🟡 در حال اتمام |
| ۶ | استقرار روی VPS (PostgreSQL، Nginx، SSL) | ⏳ در برنامه |

---

## فناوری‌ها

### بخش سرور

- **Python** 3.13.9
- **Django** 6.1.2
- **SQLite** (توسعه) / **PostgreSQL** (تولید)
- **Django Authentication و Groups** برای ورود و نقش‌ها
- **jdatetime** برای تاریخ شمسی
- **openpyxl** برای خروجی Excel
- **django-unfold** برای پنل ادمین
- **django-htmx** و **django-widget-tweaks** برای فرم‌ها

### رابط کاربری

- Django Templates
- **Tailwind CSS** (از CDN)
- **Vazirmatn** (فونت)
- **ApexCharts** (نمودارها)
- **jalalidatepicker** (تقویم شمسی)
- **Alpine.js** و **HTMX** (تعامل)
- رابط فارسی و RTL

### مدیریت محیط

- **uv** (0.12.7) برای مدیریت وابستگی‌ها
- **python-dotenv** برای `.env`

---

## ساختار پروژه

```
CRM_Digiran/
├── manage.py
├── pyproject.toml           # وابستگی‌ها (uv)
├── requirements.txt         # نسخه‌ی pip-compatible
├── uv.lock                  # قفل نسخه‌ها
├── .env                     # مقادیر محرمانه (git ignored)
├── .env.example             # نمونه
├── db.sqlite3               # دیتابیس توسعه (git ignored)
│
├── crm/                     # تنظیمات پروژه
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── accounts/                # کاربران و RBAC
│   ├── permissions.py       # ⭐ نقش‌ها و دسترسی‌ها
│   ├── context_processors.py # ⭐ دسترسی‌ها در تمپلیت
│   ├── views.py
│   ├── forms.py
│   ├── urls.py
│   └── tests.py             # ۶۱ تست
│
├── customers/               # مشتریان
├── calls/                   # تماس‌ها
├── products/                # کالاها + StockMovement
│   ├── models.py            # ⭐ Product + StockMovement
│   └── tests.py             # ۱۵ تست
│
├── sales/                   # فاکتورها
│   ├── models.py            # ⭐ Invoice + InvoiceItem
│   ├── signals.py           # ⭐ محاسبه‌ی خودکار مبالغ
│   ├── views.py             # ⭐ مدیریت اتمیک موجودی
│   └── tests.py             # ۱۸ تست
│
├── hr/                      # منابع انسانی
│   ├── models.py            # Employee, Task, LeaveRequest, Attendance
│   └── ...
│
├── dashboard/               # داشبورد و گزارشات
│   ├── views.py             # KPI، چارت‌ها، Excel
│   ├── templatetags/
│   │   └── fa_numbers.py    # فیلتر اعداد فارسی
│   └── management/commands/
│       └── backup_db.py     # بکاپ
│
├── templates/               # تمام تمپلیت‌ها
├── static/                  # فایل‌های استاتیک
├── backups/                 # بکاپ‌های دیتابیس (git ignored)
└── logs/                    # لاگ‌ها (git ignored)
```

---

## راه‌اندازی محیط توسعه

### پیش‌نیازها

- Python 3.13+
- uv (نصب: `pip install uv` یا `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Git

### ۱. کلون و setup

```bash
git clone <repo-url> CRM_Digiran
cd CRM_Digiran
```

### ۲. ساخت محیط مجازی

```bash
uv venv .venv
source .venv/bin/activate
```

**⚠️ نکته:** اگه conda فعاله، اول `conda deactivate` بزن.

### ۳. نصب وابستگی‌ها

```bash
uv sync
```

### ۴. تنظیم `.env`

```bash
cp .env.example .env
nano .env
```

مقادیر زیر رو تنظیم کن:

```env
SECRET_KEY=<یک کلید ۵۰+ کاراکتری تصادفی>
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
```

برای ساخت `SECRET_KEY`:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### ۵. مهاجرت و اجرا

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### ۶. دسترسی

- صفحه‌ی ورود: `http://127.0.0.1:8000/accounts/login/`
- پنل ادمین: `http://127.0.0.1:8000/admin/`

---

## نقش‌ها و دسترسی‌ها

سیستم **RBAC** (Role-Based Access Control) کامل دارد.

### نقش‌ها

| نقش | کلید | توضیح |
|------|------|-------|
| مدیر کل | `admin` | `is_superuser=True` — دسترسی کامل |
| مدیر فروش | `sales_manager` | مدیریت فروش و تیم |
| کارشناس فروش | `sales` | ثبت مشتری، تماس، فاکتور |
| پشتیبان | `support` | پاسخگویی و ثبت تماس |
| حسابدار | `accountant` | مدیریت فاکتورها و گزارشات مالی |
| اپراتور | `operator` | ثبت اطلاعات اولیه |

### ماتریس دسترسی خلاصه

| بخش | admin | sales_manager | sales | support | accountant | operator |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| مشتریان — مشاهده | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| مشتریان — ایجاد/ویرایش | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| مشتریان — حذف | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| کالاها — ایجاد/ویرایش | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| کالاها — حذف | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| فاکتورها — مشاهده | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| فاکتورها — ایجاد/ویرایش | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| فاکتورها — حذف | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| فاکتورها — چاپ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| تماس‌ها — ارجاع | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| پرسنل — مدیریت | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| وظایف — مدیریت | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| مرخصی — بررسی | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| حضور و غیاب | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Excel | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| مدیریت کاربران | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

### استفاده در کد

**در View:**

```python
from accounts.permissions import require_permission

@login_required
@require_permission('customers.delete')
def customer_delete(request, pk):
    ...
```

**در Template:**

```html
{% if 'customers.delete' in user_permissions %}
    <a href="...">حذف</a>
{% endif %}
```

---

## قابلیت‌ها

### ۱. احراز هویت و کاربران

- ورود/خروج با صفحه‌ی اختصاصی فارسی
- مدیریت کاربران (فقط superuser)
- تغییر رمز، فعال/غیرفعال‌سازی
- کنترل هوشمند حذف کاربر (چک رکوردهای مرتبط)

### ۲. مشتریان

- CRUD کامل + صفحه‌ی جزئیات
- جستجو، فیلتر (وضعیت، منبع، کارمند)، صفحه‌بندی
- KPI: کل، فعال، بالقوه
- نمایش آخرین تماس‌ها و فاکتورها

### ۳. تماس‌ها

- ثبت تماس ورودی/خروجی
- ارجاع به کارمند دیگر (AJAX + فرم)
- پیگیری با تاریخ شمسی
- منطق هماهنگی `status` و `is_followed_up`

### ۴. کالا و انبار

- مدیریت کالاها (SKU، دسته، قیمت، موجودی)
- **`StockMovement`:** لاگ کامل گردش موجودی
- **`change_stock()`:** تغییر اتمیک با `select_for_update`
- جلوگیری از کسری با `ValueError`

### ۵. فاکتورها

- فاکتور چند قلمی
- شماره‌ی خودکار شمسی: `INV-140507-0001`
- **Signal** برای محاسبه‌ی خودکار مبالغ
- کاهش/برگشت خودکار موجودی
- چاپ حرفه‌ای با A4

### ۶. منابع انسانی

- پرسنل، وظایف، مرخصی، حضور و غیاب
- گزارش ماهانه‌ی شمسی
- پروفایل شخصی هر کاربر

### ۷. داشبورد و گزارشات

- KPI با فیلتر تاریخ شمسی
- نمودارهای تعاملی (ApexCharts)
- خروجی Excel (۵ شیت)
- اعداد فارسی

### ۸. بکاپ

- فرمان `python manage.py backup_db`
- فشرده‌سازی gzip
- نگهداری ۳۰ روزه
- حذف خودکار قدیمی‌ها

---

## نشانی‌های محلی

| کاربرد | آدرس |
|--------|------|
| داشبورد | `http://127.0.0.1:8000/` |
| ورود | `http://127.0.0.1:8000/accounts/login/` |
| پنل ادمین | `http://127.0.0.1:8000/admin/` |
| مشتریان | `http://127.0.0.1:8000/customers/` |
| تماس‌ها | `http://127.0.0.1:8000/calls/` |
| کالاها | `http://127.0.0.1:8000/products/` |
| فاکتورها | `http://127.0.0.1:8000/invoices/` |
| منابع انسانی | `http://127.0.0.1:8000/hr/` |

---

## بکاپ دیتابیس

### دستی

```bash
cd ~/CRM_Digiran
source .venv/bin/activate

# با فشرده‌سازی (پیش‌فرض)
python manage.py backup_db

# بدون فشرده‌سازی
python manage.py backup_db --no-compress

# نگهداری ۶۰ روزه
python manage.py backup_db --keep-days 60
```

### بکاپ خودکار (cron)

```bash
crontab -e
```

اضافه کن:

```cron
# هر روز ساعت ۲ بامداد
0 2 * * * cd /home/USER/CRM_Digiran && /home/USER/CRM_Digiran/.venv/bin/python manage.py backup_db >> /home/USER/CRM_Digiran/logs/backup.log 2>&1
```

### بازیابی

```bash
# ۱. سرور رو متوقف کن
# ۲. دیتابیس فعلی رو جابه‌جا کن
mv db.sqlite3 db.sqlite3.old

# ۳. بکاپ رو باز کن
gunzip -c backups/db-backup-YYYYMMDD-HHMMSS.sqlite3.gz > db.sqlite3

# ۴. سرور رو راه‌اندازی کن
python manage.py runserver
```

---

## تست‌ها

### اجرای همه‌ی تست‌ها

```bash
python manage.py test
```

### اجرای تست‌های یک اپ

```bash
python manage.py test accounts -v 2
python manage.py test products
python manage.py test sales
```

### پوشش فعلی

| اپ | تعداد | موضوع |
|-----|-------|-------|
| accounts | ۶۱ | RBAC، permissions، decoratorها، ماتریس، Integration |
| products | ۱۵ | StockMovement، change_stock، properties |
| sales | ۱۸ | Signal، شماره شمسی، calculate_totals |

---

## استقرار روی سرور

### پیش‌نیازها

- Ubuntu 22.04+ یا مشابه
- PostgreSQL 14+
- Nginx
- Python 3.13

### خلاصه‌ی مراحل

1. **PostgreSQL:** نصب و ساخت دیتابیس
2. **تنظیم `.env` تولید:**
   ```env
   DEBUG=False
   SECRET_KEY=<کلید تصادفی ۵۰+ کاراکتری>
   ALLOWED_HOSTS=example.com,www.example.com
   CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com
   DATABASE_URL=postgres://user:pass@localhost:5432/crm_digiran
   ```
3. **`python manage.py migrate`**
4. **`python manage.py collectstatic`**
5. **Gunicorn + systemd** برای اجرای دائمی Django
6. **Nginx** به‌عنوان reverse proxy
7. **Let's Encrypt** برای HTTPS
8. **بکاپ خودکار** با cron

### نمونه systemd service

```ini
[Unit]
Description=CRM Digiran Gunicorn
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/home/USER/CRM_Digiran
Environment="PATH=/home/USER/CRM_Digiran/.venv/bin"
ExecStart=/home/USER/CRM_Digiran/.venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/run/crm.sock \
    crm.wsgi:application

[Install]
WantedBy=multi-user.target
```

### نمونه Nginx config

```nginx
server {
    listen 80;
    server_name example.com www.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name example.com www.example.com;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    client_max_body_size 20M;

    location /static/ {
        alias /home/USER/CRM_Digiran/staticfiles/;
    }

    location /media/ {
        alias /home/USER/CRM_Digiran/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/crm.sock;
    }
}
```

---

## نکات امنیتی

### مقادیر حساس

- `.env` هرگز نباید در Git باشد
- `db.sqlite3` هرگز نباید commit شود
- `backups/` حاوی داده‌های حساس است
- `SECRET_KEY` باید ۵۰+ کاراکتر تصادفی باشد
- در production حتماً `DEBUG=False`

### چک قبل از انتشار

```bash
DEBUG=False SECRET_KEY='<real-key>' python manage.py check --deploy
```

باید `System check identified no issues (0 silenced)` بده.

### اگه رمز یا کلید لو رفت

- `SECRET_KEY` رو عوض کن (خروج خودکار همه)
- رمز کاربران مربوطه رو عوض کن
- Application Password ها رو لغو کن

---

## مجوز

این پروژه اختصاصی است. تمامی حقوق محفوظ است.