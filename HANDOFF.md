# 🤖 HANDOFF — سند تحویل پروژه CRM Digiran

> **این فایل رو کامل بخون. تمام اطلاعاتی که برای ادامه‌ی پروژه نیاز داری اینجاست.**
> بعد از خوندن، مستقیم برو سراغ بخش ۱۱ (کار بعدی).

---

## ۱. شناسنامه‌ی پروژه

**نام:** CRM Digiran  
**هدف:** سیستم مدیریت ارتباط با مشتریان و عملیات داخلی  
**Django:** 6.1.2  
**Python:** 3.13.9  
**مسیر:** `~/CRM_Digiran/`  
**Branch:** `master`  
**آخرین commit:** `feat: soft delete, CustomerNote, Category model, dashboard user filter`  
**آخرین فاز تکمیل‌شده:** ۷.۳ (Category Model)  
**کار بعدی:** ۷.۴ (N+1 Optimization)

---

## ۲. محیط توسعه

### ۲.۱ فعال‌سازی محیط
```bash
cd ~/CRM_Digiran
source .venv/bin/activate
```

### ۲.۲ ⚠️ نکات حیاتی محیط
- **`uv` نه `pip`**: پروژه با `uv` مدیریت می‌شه. `pip` توی venv **نصب نیست**.
  - ❌ `pip install X`
  - ✅ `uv pip install X`
  - ✅ `uv pip list`
- **conda رو خاموش کن**: اگه پرامپت `(base)` یا `(crm-digiran)` دیدی، اول `conda deactivate` بزن.
- **پرامپت درست**: `(.venv)` یا `(crm-digiran)` — نه `(base)`
- **paste چندخطی در shell**: `manage.py shell` با paste چندخطی خطا می‌ده. از اینا استفاده کن:
  - `python manage.py shell -c "..."`
  - `python manage.py shell < /tmp/script.py`

### ۲.۳ وابستگی‌ها
```
Django==6.1.2
django-unfold==0.108.0
django-htmx==1.29.0
django-widget-tweaks==1.5.1
jdatetime==6.1.0
jalali-core==1.0.0
openpyxl==3.1.5
pillow==12.3.0
psycopg2-binary==2.9.13
python-dotenv==1.2.4
```

### ۲.۴ دستورات رایج
```bash
python manage.py check
python manage.py runserver
python manage.py makemigrations
python manage.py migrate
python manage.py test
python manage.py test accounts -v 2       # یک اپ
python manage.py shell
python manage.py shell -c "..."
python manage.py showmigrations
python manage.py sqlmigrate app_name 000X
```

---

## ۳. ساختار پروژه

```
CRM_Digiran/
├── manage.py
├── pyproject.toml / requirements.txt / uv.lock
├── .env                          # git ignored
├── .env.example
├── db.sqlite3                    # git ignored
├── HANDOFF.md                    # ⭐ این فایل
├── SESSION_NOTES.md              # یادداشت جلسه‌ی قبلی
│
├── crm/
│   ├── settings.py               # env-driven: DEBUG, SECRET_KEY, ALLOWED_HOSTS, DATABASE_URL
│   ├── urls.py
│   └── wsgi.py / asgi.py
│
├── accounts/
│   ├── permissions.py            # ⭐ RBAC core (نقش‌ها، دسترسی‌ها، decoratorها)
│   ├── context_processors.py     # user_permissions در تمپلیت
│   ├── views.py / forms.py / urls.py
│   └── tests.py                  # ۶۱ تست
│
├── customers/
│   ├── models.py                 # Customer + CustomerNote
│   ├── views.py                  # customer CRUD + note CRUD (AJAX)
│   ├── forms.py / urls.py / admin.py
│   └── migrations/               # 0001, 0002, 0003 (CustomerNote)
│
├── calls/
│   ├── models.py                 # Call با منطق followup/status
│   ├── views.py                  # + call_reassign (AJAX + فرم)
│   └── migrations/               # 0001-0003
│
├── products/
│   ├── models.py                 # ⭐ Category + Product + ProductManager + StockMovement
│   ├── views.py                  # product CRUD + 4 view دسته‌بندی
│   ├── forms.py                  # ProductForm + CategoryForm
│   ├── admin.py / urls.py
│   ├── tests.py                  # ۱۵ تست
│   └── migrations/               # 0001-0007 (Category پیچیده)
│
├── sales/
│   ├── models.py                 # Invoice + InvoiceItem (شماره شمسی)
│   ├── signals.py                # calculate_totals خودکار
│   ├── views.py                  # + _apply_invoice_stock, _reverse_invoice_stock
│   ├── apps.py                   # ready() برای ثبت signal
│   ├── tests.py                  # ۱۸ تست
│   └── migrations/
│
├── hr/
│   ├── models.py                 # Employee (user=SET_NULL) + Task + LeaveRequest + Attendance
│   ├── views.py / forms.py / urls.py
│   └── migrations/               # 0001-0003
│
├── dashboard/
│   ├── views.py                  # ⭐ KPI + فیلتر کاربر (فقط مدیرها)
│   ├── templatetags/fa_numbers.py # fa_num, fa_price, fa_digits, fa_date
│   └── management/commands/backup_db.py
│
├── templates/
│   ├── base.html                 # ⭐ سایدبار شرطی + لوگو + پیام‌های رنگی
│   ├── accounts/ (login, user_list, user_form, ...)
│   ├── customers/ (list, detail, form)
│   ├── calls/ (list, detail, form, reassign, confirm_delete)
│   ├── products/ (list, detail, form, confirm_delete, restore,
│   │              category_list, category_form, category_confirm_delete)
│   ├── sales/ (list, detail, form, confirm_delete, print)
│   ├── hr/ (~15 فایل)
│   └── dashboard/ (home, search)
│
├── static/
│   ├── images/logo.gif
│   └── vendor/jalalidatepicker/
│
├── backups/                      # git ignored
└── logs/                         # git ignored
```

---

## ۴. فازهای تکمیل‌شده

### ✅ فاز ۱ — پاکسازی محیط
- `pyproject.toml`, `requirements.txt`, `uv.lock` هم‌خوان
- `src/crm_digiran/` (باقی‌مانده‌ی uv init) حذف شد
- `.gitignore` کامل

### ✅ فاز ۲ — مسائل بحرانی
- `Employee.user`: `CASCADE` → `SET_NULL`
- `user_delete`: چک رکوردهای مرتبط (تماس، فاکتور، پرسنل)
- **`StockMovement`** + `Product.change_stock()` اتمیک با `select_for_update`
- `sales/views.py`: `_apply_invoice_stock`, `_reverse_invoice_stock`
- `calls/reassign.html` ساخته شد + پشتیبانی AJAX/فرم

### ✅ فاز ۳ — هم‌خوانی و باگ‌ها
- Signal `post_save`/`post_delete` روی `InvoiceItem` → `calculate_totals` خودکار
- شماره فاکتور شمسی: `INV-140507-0001` (با `jdatetime`)
- `json.dumps` + `json_script` برای چارت‌ها (ضد XSS)
- `calls_this_month` با ماه شمسی
- فلگ `--no-compress` در `backup_db.py`
- autofill قیمت در فرم فاکتور (با `json_script` + JS)
- `{% load fa_numbers %}` سراسری
- پیام‌های رنگی در `base.html` (error/warning/info/success)

### ✅ فاز ۴ — RBAC
- `accounts/permissions.py`: ۶ نقش، ~۲۹ دسترسی
- `accounts/context_processors.py`: `user_permissions` در همه‌ی تمپلیت‌ها
- اعمال روی همه‌ی اپ‌ها (customers, calls, products, sales, hr, dashboard)
- سایدبار شرطی
- ۶۱ تست

### ✅ فاز ۵ — تست + آماده‌سازی production
- ۹۴ تست (accounts 61 + products 15 + sales 18)
- `settings.py`: `DEBUG`/`SECRET_KEY`/`ALLOWED_HOSTS`/`DATABASE_URL` از env
- `SECURE_*` settings برای production
- LOGGING با `RotatingFileHandler`
- `.env.example` کامل
- `check --deploy` پاس

### ✅ ۷.۱ — Soft delete برای Product
- `Product.is_deleted`, `deleted_at`
- `ProductManager` (پیش‌فرض = فقط حذف‌نشده) + `all_objects`
- متدهای `delete()` (soft)، `hard_delete()`، `restore()`
- `product_list` با `?show=deleted`
- `product_restore` view + URL
- `templates/products/restore.html`

### ✅ ۷.۲ — CustomerNote
- مدل: `customer`, `text`, `created_by`, `is_pinned`, `created_at`, `updated_at`
- `can_edit(user)`: نویسنده یا سوپریوزر
- Viewهای AJAX: `note_create`, `note_edit`, `note_delete`, `note_toggle_pin`
- بخش یادداشت در `customers/detail.html` با JS
- یادداشت قدیمی (`Customer.notes`) کنار جدیدها نمایش داده می‌شه

### ✅ ۷.۳ — Category Model
- مدل `Category`: `name`, `slug`, `icon`, `order`, `is_active`
- `Product.category`: `CharField` → `ForeignKey` (پیچیده‌ترین migration: 0005→0007)
- CRUD کامل در خود CRM (نه فقط admin):
  - `products/category_list.html`
  - `products/category_form.html`
  - `products/category_confirm_delete.html`
- Permission جدید: `categories.view` و `categories.manage`
- ۶ دسته‌ی پیش‌فرض: 📱 موبایل، 💻 لپ‌تاپ، 🎧 لوازم جانبی، 🔧 قطعات، 🛠️ خدمات، 📦 سایر

### ✅ فیلتر کاربر در داشبورد
- `_is_manager(user)`: سوپریوزر یا گروه «مدیر فروش»
- `_get_data_owner(user, filter_user_id)`: تعیین مالک داده
- `_filtered_customers/calls/invoices(owner)`
- dropdown «کارمند» فقط برای مدیرها
- بنر «فیلتر فعال» (زرد) + «نمایش داده‌های شخصی» (آبی)
- Excel با پارامتر `employee`

### ✅ لوگوی سایدبار
- `base.html`: `<img src="{% static 'images/logo.gif' %}">` با fallback به `C`

---

## ۵. ماتریس دسترسی کامل

| بخش | admin | sales_manager | sales | support | accountant | operator |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| مشتریان — مشاهده | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| مشتریان — ایجاد/ویرایش | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| مشتریان — حذف | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| تماس‌ها — مشاهده | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| تماس‌ها — ایجاد/ویرایش | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| تماس‌ها — ارجاع | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| تماس‌ها — حذف | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| کالاها — مشاهده | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| کالاها — ایجاد/ویرایش | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| کالاها — حذف (soft) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| دسته‌بندی — مشاهده | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| دسته‌بندی — مدیریت | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| فاکتورها — مشاهده | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| فاکتورها — ایجاد/ویرایش | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| فاکتورها — حذف | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| فاکتورها — چاپ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| پرسنل — مشاهده | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| پرسنل — مدیریت | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| وظایف — مشاهده/مدیریت | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| مرخصی — بررسی | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| حضور و غیاب | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| داشبورد | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| فیلتر کاربر در داشبورد | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Excel | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| مدیریت کاربران | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

### نحوه‌ی استفاده در کد

**View:**
```python
from accounts.permissions import require_permission, has_permission

@login_required
@require_permission('customers.delete')
def my_view(request):
    ...
```

**Template:**
```html
{% if 'customers.delete' in user_permissions %}
    <a href="...">حذف</a>
{% endif %}
```

**تابع کمکی:**
```python
from accounts.permissions import (
    has_permission, has_role, get_user_role, get_user_permissions,
    ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES,
    ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_OPERATOR,
)

if has_permission(request.user, 'products.delete'):
    ...
```

---

## ۶. تصمیمات معماری مهم

1. **پروژه‌ی مستقل Django** — نه اتصال به WordPress/FluentCRM
2. **SQLite (توسعه) / PostgreSQL (تولید)** — با `DATABASE_URL` env
3. **`StockMovement`**: هر تغییر موجودی، یک رکورد با `before/after`
4. **`Product.change_stock()`**: اتمیک با `select_for_update`، `ValueError` در کسری
5. **Soft delete برای Product**: `is_deleted` + `ProductManager` + `all_objects`
6. **`CustomerNote`** به‌جای `TextField` برای یادداشت‌ها
7. **`Category` مدل** (نه `choices` ثابت)
8. **RBAC در View + Template**: نه فقط Template
9. **Signal برای `calculate_totals`**: قابل اتکا در همه‌ی مسیرها
10. **`json_script` برای داده‌های JS**: ضد XSS
11. **تاریخ شمسی سراسری**: با `jdatetime` و `data-jdp`
12. **شماره فاکتور شمسی**: `INV-YYMM-XXXX` (مثلاً `INV-140507-0001`)

---

## ۷. نکات و تله‌های مهم

### ⚠️ محیط
- `pip` توی venv نیست → `uv pip`
- conda و venv قاطی می‌شن → `conda deactivate` اول
- paste چندخطی در shell خطا می‌ده → از `shell -c` یا `shell < script.py`

### ⚠️ کد
- **`Invoice.save()` رو دستی صدا نزن** برای `calculate_totals` — signal انجام می‌ده
- **`product.stock = X` مستقیم نذار** — از `change_stock(X - current, ...)`
- **`Product.objects`** = فقط حذف‌نشده‌ها | **`Product.all_objects`** = همه
- **`QuerySet.delete()` گروهی** signal `post_delete` رو trigger نمی‌کنه
- **`Employee.user` روی `SET_NULL`** — حذف کاربر پروفایل HR رو حفظ می‌کنه
- **`Category` روی `PROTECT`** — دسته‌ی دارای کالا قابل حذف نیست
- **`Invoice.customer` روی `PROTECT`** — مشتری با فاکتور قابل حذف نیست
- **`InvoiceItem.product` روی `PROTECT`** — کالای توی فاکتور قابل حذف نیست
- **`StockMovement.product` روی `PROTECT`** — کالای دارای گردش قابل حذف نیست

### ⚠️ RBAC
- هر view جدید → `@require_permission('x.y')`
- هر دکمه‌ی جدید → `{% if 'x.y' in user_permissions %}`
- هر دسترسی جدید → توی `PERMISSIONS` dict در `accounts/permissions.py`
- `superuser` همه‌ی دسترسی‌ها رو خودکار داره

### ⚠️ Git
- branch: `master`
- git ignored: `.env`, `db.sqlite3`, `backups/`, `logs/`, `.venv/`, `staticfiles/`, `*.sqlite3`, `*:Zone.Identifier`
- فایل‌های `:Zone.Identifier` (ویندوز) توی `.gitignore`

---

## ۸. کاربران تست

- **`admin`** — سوپریوزر
- **`test`** — نقش support

ساخت کاربر جدید:
```python
from django.contrib.auth.models import User, Group
from accounts.forms import ROLE_GROUP_MAP

u = User.objects.create_user(username='test_sales', password='test1234')
u.is_staff = True
g, _ = Group.objects.get_or_create(name=ROLE_GROUP_MAP['sales'])
u.groups.add(g)
u.save()
```

---

## ۹. دستورات مفید

### اجرای تست
```bash
python manage.py test -v 1
python manage.py test accounts -v 2
python manage.py test products sales
```

### تست یک اسکریپت
```bash
python manage.py shell -c "
from products.models import Product, Category
for c in Category.objects.all():
    print(f'{c.icon} {c.name}: {c.products_count} کالا')
"
```

### بکاپ
```bash
python manage.py backup_db
python manage.py backup_db --no-compress
python manage.py backup_db --keep-days 60
```

### چک امنیتی production
```bash
DEBUG=False SECRET_KEY="$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')" python manage.py check --deploy
```

---

## ۱۰. فازهای باقی‌مانده (نقشه‌ی راه)

### 🔴 ۷.۴ — N+1 Optimization (کار بعدی)
**هدف:** بهینه‌سازی کوئری‌های تکراری

**فایل‌های درگیر:**
1. **`hr/views.py` — `attendance_report`**
   - الان: برای هر کارمند ۵ کوئری جدا
   - راه‌حل: `annotate` + `Count` + `Sum` با `Case/When`
   
2. **`products/views.py` — `product_detail`**
   - الان: `sum()` روی Python loop
   - راه‌حل: `.aggregate(Sum('quantity'))` و `.aggregate(Sum('total_price'))`
   
3. **`dashboard/views.py` — `_get_dashboard_data`**
   - الان: کوئری‌های تکراری `_filtered_invoices(owner)` چند بار
   - راه‌حل: cache کردن queryset در متغیر

**نکات:**
- قبل از تغییر، با `python manage.py shell` و `connection.queries` تعداد کوئری‌ها رو بشمار
- بعد از تغییر، همون تعداد رو چک کن که کم شده باشه
- تست‌ها بعد از تغییر باید پاس بشن

### 🔴 ۷.۵ — چک تکراری مشتری
- `Customer.mobile` و `Customer.national_id` تکراری
- راه‌حل: `clean()` در فرم + هشدار به کاربر (نه بلاک سخت)

### 🟡 ۷.۶ — فیلترهای پیشرفته
- گزارش فروش با فیلتر کارمند + بازه
- لیست مشتریان با فیلتر تلفیقی (وضعیت + منبع + مسئول)

### 🟡 ۷.۷ — صفحه‌ی مستقل BI
- صفحه‌ی جدا از داشبورد با گزارش‌های عمیق‌تر

### 🟡 ۷.۸ — ورود از Excel
- آپلود Excel برای مشتریان/کالاها
- استفاده از `openpyxl` (نصب‌شده)

### 🟡 ۷.۹ — InvoiceLog (audit trail)
- ثبت هر تغییر فاکتور (کی، کِی، چی عوض شد)

### 🟡 ۷.۱۰ — بهبود فرم فاکتور
- autocomplete کالا (به‌جای dropdown طولانی)
- افزودن سطر جدید با JS

### 🟢 ۸.۱ — صفحه‌ی 403 سفارشی
- جای redirect به داشبورد، یه صفحه‌ی «دسترسی ندارید»

### 🟢 ۸.۲ — Rate limiting روی login
- جلوگیری از brute force

### 🟢 ۸.۳ — 2FA برای admin
- با `django-otp` یا مشابه

### 🟢 ۸.۴ — Audit log سراسری
- ثبت همه‌ی تغییرات حساس

### ⏸️ فاز ۶ — استقرار روی VPS (به تعویق افتاده)
- PostgreSQL
- Gunicorn + systemd
- Nginx
- SSL با Let's Encrypt
- Cron برای بکاپ
- این فاز **نیاز به VPS داره** و تا آماده نشدن، انجام نمی‌شه

---

## ۱۱. 🎯 کار بعدی: ۷.۴ — N+1 Optimization

### ۱۱.۱ درخواست از ایجنت
```
از ۷.۴ شروع کن. اول فایل‌های hr/views.py, products/views.py, dashboard/views.py رو 
بخون و بعد پیشنهاد بده کدوم کوئری‌ها N+1 هستن.
```

### ۱۱.۲ سه بخش اصلی بهینه‌سازی

**بخش ۱: `hr/attendance_report`**
- فایل: `hr/views.py`
- مشکل: حلقه روی کارمندان، ۵ کوئری per کارمند
- راه‌حل: `annotate` با `Count` و `Sum`

**بخش ۲: `products/detail`**
- فایل: `products/views.py`
- مشکل: `sum()` روی لیست کامل در Python
- راه‌حل: `.aggregate(Sum('quantity'))` و `.aggregate(Sum('total_price'))`

**بخش ۳: `dashboard/_get_dashboard_data`**
- فایل: `dashboard/views.py`
- مشکل: `_filtered_invoices(owner)` چند بار تکرار می‌شه
- راه‌حل: cache در متغیر + `select_related` و `prefetch_related`

### ۱۱.۳ نکات اجرا
- قبل از تغییر، تعداد کوئری‌ها رو با `connection.queries` اندازه‌گیری کن
- بعد از تغییر، همون تست رو دوباره اجرا کن
- تست‌های موجود باید پاس بمونن
- اگه کوئری به `< ۱۰` رسید، موفقیت‌آمیزه

---

## ۱۲. ✅ چک‌لیست شروع چت جدید

```
[ ] این فایل (HANDOFF.md) رو کامل خوندم
[ ] محیط رو با `source .venv/bin/activate` فعال کردم
[ ] `python manage.py check` رو زدم → پاس شد
[ ] `git log --oneline -3` رو دیدم → آخرین commit درسته
[ ] `python manage.py test -v 1` رو زدم → ۹۴ تست پاس
[ ] آماده‌ی شروع ۷.۴ هستم
```

---

## ۱۳. 📞 درخواست نهایی از ایجنت

**لطفاً از ۷.۴ (N+1 Optimization) شروع کن.**

اول:
1. `hr/views.py`, `products/views.py`, `dashboard/views.py` رو بخون
2. لیست کوئری‌های N+1 رو شناسایی کن
3. راه‌حل پیشنهاد بده
4. بعد از تأیید، کد اصلاحی رو کامل بفرست

**قبل از هر تغییری، مطمئن شو:**
- `python manage.py check` پاس می‌شه
- `python manage.py test` پاس می‌شه
- دیتابیس بکاپ داره

**آماده‌ام. شروع کن!** 🚀

---

## پیوست: اطلاعات تماس و لینک‌ها

- **مسیر پروژه:** `~/CRM_Digiran/`
- **آدرس محلی:** `http://127.0.0.1:8000/`
- **پنل ادمین:** `http://127.0.0.1:8000/admin/`
- **ورود:** `http://127.0.0.1:8000/accounts/login/`
- **README کامل:** `~/CRM_Digiran/README.md`
- **یادداشت جلسه:** `~/CRM_Digiran/SESSION_NOTES.md`
- **آخرین snapshot:** `~/crm-digiran-snapshot-*.tar.gz`

---

**پایان سند. حالا برو ۷.۴ رو شروع کن.** ✅
