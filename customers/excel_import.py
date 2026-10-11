"""ورود مشتریان از Excel — فاز ۷.۸"""
from django.contrib.auth.models import User

from crm.excel_utils import (
    build_xlsx, normalize_digits, parse_jalali_date, read_xlsx, resolve_choice,
)
from .models import Customer


# ═══════════════════════════════════════════════════
# نگاشت ستون‌ها
# ═══════════════════════════════════════════════════
CUSTOMER_HEADER_MAP = {
    'نام': 'name',
    'شماره تماس': 'mobile',
    'ایمیل': 'email',
    'کد ملی': 'national_id',
    'تاریخ تولد': 'birth_date',
    'وضعیت': 'status',
    'منبع': 'source',
    'کارمند مسئول': 'assigned_to',
    'آدرس': 'address',
    'یادداشت': 'notes',
}

REQUIRED_COLUMNS = ['نام', 'شماره تماس']


# ═══════════════════════════════════════════════════
# Parse + Validate
# ═══════════════════════════════════════════════════
def parse_customer_excel(file_obj, max_rows=1000):
    """Returns dict با rows/header_errors/total/valid/invalid"""
    data_rows, missing = read_xlsx(file_obj, CUSTOMER_HEADER_MAP, max_rows=max_rows)

    header_errors = [col for col in REQUIRED_COLUMNS if col in missing]
    if header_errors:
        return {
            'rows': [],
            'header_errors': header_errors,
            'total': 0, 'valid': 0, 'invalid': 0,
        }

    seen_mobiles = {}
    seen_nids = {}
    rows = []
    valid_count = 0

    for raw in data_rows:
        cleaned, errors = _validate_customer_row(raw, seen_mobiles, seen_nids)
        is_valid = len(errors) == 0
        if is_valid:
            valid_count += 1
        rows.append({
            'row_num': raw['_row_num'],
            'data': cleaned,
            'raw': {k: raw.get(k) for k in CUSTOMER_HEADER_MAP.values()},
            'errors': errors,
            'is_valid': is_valid,
        })

    return {
        'rows': rows,
        'header_errors': [],
        'total': len(rows),
        'valid': valid_count,
        'invalid': len(rows) - valid_count,
    }


def _validate_customer_row(raw, seen_mobiles, seen_nids):
    errors = []
    cleaned = {}

    # ─── نام ───
    name = str(raw.get('name') or '').strip()
    if not name:
        errors.append('نام الزامی است')
    elif len(name) > 200:
        errors.append('نام بیش از ۲۰۰ کاراکتر است')
    cleaned['name'] = name

    # ─── موبایل ───
    mobile = normalize_digits(raw.get('mobile'))
    for ch in (' ', '-', '(', ')'):
        mobile = mobile.replace(ch, '')

    if not mobile:
        errors.append('شماره تماس الزامی است')
    elif not mobile.isdigit():
        errors.append('شماره تماس باید فقط شامل ارقام باشد')
    elif len(mobile) > 15:
        errors.append('شماره تماس بیش از ۱۵ رقم است')
    elif mobile in seen_mobiles:
        errors.append(f'شماره تماس تکراری در فایل (ردیف {seen_mobiles[mobile]})')
    else:
        seen_mobiles[mobile] = raw['_row_num']
        if Customer.objects.filter(mobile=mobile).exists():
            errors.append('شماره تماس قبلاً در سیستم ثبت شده')
    cleaned['mobile'] = mobile

    # ─── ایمیل ───
    email = str(raw.get('email') or '').strip()
    if email:
        parts = email.split('@')
        if len(parts) != 2 or '.' not in parts[1]:
            errors.append('ایمیل نامعتبر')
    cleaned['email'] = email or None

    # ─── کد ملی ───
    nid = normalize_digits(raw.get('national_id'))
    for ch in (' ', '-'):
        nid = nid.replace(ch, '')
    if nid:
        if not nid.isdigit():
            errors.append('کد ملی باید فقط شامل ارقام باشد')
        elif len(nid) != 10:
            errors.append('کد ملی باید دقیقاً ۱۰ رقم باشد')
        elif nid in seen_nids:
            errors.append(f'کد ملی تکراری در فایل (ردیف {seen_nids[nid]})')
        else:
            seen_nids[nid] = raw['_row_num']
            if Customer.objects.filter(national_id=nid).exists():
                errors.append('کد ملی قبلاً در سیستم ثبت شده')
    cleaned['national_id'] = nid or None

    # ─── تاریخ تولد ───
    bd_raw = raw.get('birth_date')
    if bd_raw:
        bd = parse_jalali_date(bd_raw)
        if bd is None:
            errors.append('تاریخ تولد نامعتبر (فرمت: ۱۳۷۸/۱۲/۱۶)')
        cleaned['birth_date'] = bd
    else:
        cleaned['birth_date'] = None

    # ─── وضعیت ───
    cleaned['status'] = resolve_choice(
        raw.get('status'), Customer.STATUS_CHOICES, default='lead',
    )

    # ─── منبع ───
    cleaned['source'] = resolve_choice(
        raw.get('source'), Customer.SOURCE_CHOICES, default='direct',
    )

    # ─── کارمند مسئول ───
    assigned_raw = str(raw.get('assigned_to') or '').strip()
    assigned_user = None
    if assigned_raw:
        assigned_user = (
            User.objects.filter(username=assigned_raw).first()
            or User.objects.filter(first_name__iexact=assigned_raw).first()
            or User.objects.filter(last_name__iexact=assigned_raw).first()
        )
        if not assigned_user:
            errors.append(f'کارمند «{assigned_raw}» یافت نشد')
    cleaned['assigned_to'] = assigned_user

    # ─── آدرس و یادداشت ───
    cleaned['address'] = str(raw.get('address') or '').strip() or None
    cleaned['notes'] = str(raw.get('notes') or '').strip() or None

    return cleaned, errors


# ═══════════════════════════════════════════════════
# ذخیره
# ═══════════════════════════════════════════════════
def save_valid_customers(rows, user):
    """ذخیره‌ی فقط ردیف‌های معتبر. Returns {created, skipped, errors}"""
    created = 0
    skipped = 0
    errors = []

    for row in rows:
        if not row['is_valid']:
            skipped += 1
            continue
        try:
            Customer.objects.create(created_by=user, **row['data'])
            created += 1
        except Exception as e:
            skipped += 1
            errors.append(f"ردیف {row['row_num']}: {e}")

    return {'created': created, 'skipped': skipped, 'errors': errors}


# ═══════════════════════════════════════════════════
# قالب
# ═══════════════════════════════════════════════════
def build_customer_template():
    """قالب Excel مشتریان — با شیت راهنمای مقادیر مجاز"""
    headers = list(CUSTOMER_HEADER_MAP.keys())
    sample = [
        'علی رضایی', '09121234567', 'ali@example.com', '1234567890',
        '1378/12/16', 'بالقوه (لید)', 'وبسایت', 'admin',
        'تهران، خیابان ولیعصر', 'مشتری نمونه',
    ]
    notes = [
        'راهنمای تکمیل:',
        '• ستون‌های «نام» و «شماره تماس» الزامی هستند.',
        '• تاریخ تولد به شمسی، مثل: ۱۳۷۸/۱۲/۱۶ (یا خالی بگذارید)',
        '• کارمند مسئول: نام کاربری یا نام کامل (اختیاری)',
        '• شماره تماس یا کد ملی تکراری در سیستم رد می‌شود.',
        '• برای دیدن مقادیر مجاز دقیق، به شیت «راهنما» بروید.',
    ]

    # ─── لیست کارمندان فعال ───
    from django.contrib.auth.models import User
    staff_users = (
        User.objects
        .filter(is_active=True, is_staff=True)
        .order_by('first_name', 'last_name', 'username')
    )
    staff_items = []
    for u in staff_users:
        full_name = f"{u.first_name} {u.last_name}".strip() or u.username
        staff_items.append((u.username, f"{full_name} — {u.email or '—'}"))
    if not staff_items:
        staff_items.append(('—', 'هیچ کارمند فعالی تعریف نشده'))

    choices_sections = [
        {
            'title': 'وضعیت مشتری (ستون: وضعیت)',
            'column': 'وضعیت',
            'items': list(Customer.STATUS_CHOICES),
        },
        {
            'title': 'منبع جذب (ستون: منبع)',
            'column': 'منبع',
            'items': list(Customer.SOURCE_CHOICES),
        },
        {
            'title': 'کارمندان فعال (ستون: کارمند مسئول)',
            'column': 'کارمند مسئول',
            'items': staff_items,
        },
    ]

    return build_xlsx(
        headers,
        sample_row=sample,
        notes=notes,
        choices_sections=choices_sections,
    )