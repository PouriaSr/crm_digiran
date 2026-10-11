"""ورود کالاها از Excel — فاز ۷.۸"""
from crm.excel_utils import (
    build_xlsx, normalize_digits, parse_int, read_xlsx, resolve_choice,
)
from .models import Category, Product


PRODUCT_HEADER_MAP = {
    'نام کالا': 'name',
    'کد کالا': 'code',
    'دسته‌بندی': 'category',
    'واحد': 'unit',
    'قیمت فروش': 'price',
    'قیمت خرید': 'cost_price',
    'موجودی': 'stock',
    'حداقل موجودی': 'min_stock',
    'توضیحات': 'description',
}

REQUIRED_COLUMNS = ['نام کالا', 'کد کالا', 'دسته‌بندی']


def parse_product_excel(file_obj, max_rows=2000):
    """Returns dict با rows/header_errors/total/valid/invalid"""
    data_rows, missing = read_xlsx(file_obj, PRODUCT_HEADER_MAP, max_rows=max_rows)

    header_errors = [col for col in REQUIRED_COLUMNS if col in missing]
    if header_errors:
        return {
            'rows': [],
            'header_errors': header_errors,
            'total': 0, 'valid': 0, 'invalid': 0,
        }

    seen_codes = {}
    rows = []
    valid_count = 0

    for raw in data_rows:
        cleaned, errors = _validate_product_row(raw, seen_codes)
        is_valid = len(errors) == 0
        if is_valid:
            valid_count += 1
        rows.append({
            'row_num': raw['_row_num'],
            'data': cleaned,
            'raw': {k: raw.get(k) for k in PRODUCT_HEADER_MAP.values()},
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


def _validate_product_row(raw, seen_codes):
    errors = []
    cleaned = {}

    # ─── نام ───
    name = str(raw.get('name') or '').strip()
    if not name:
        errors.append('نام کالا الزامی است')
    elif len(name) > 200:
        errors.append('نام کالا بیش از ۲۰۰ کاراکتر است')
    cleaned['name'] = name

    # ─── کد ───
    code = normalize_digits(raw.get('code')).replace(' ', '')
    if not code:
        errors.append('کد کالا الزامی است')
    elif len(code) > 50:
        errors.append('کد کالا بیش از ۵۰ کاراکتر است')
    elif code in seen_codes:
        errors.append(f'کد کالا تکراری در فایل (ردیف {seen_codes[code]})')
    else:
        seen_codes[code] = raw['_row_num']
        if Product.all_objects.filter(code=code).exists():
            errors.append('کد کالا قبلاً در سیستم ثبت شده')
    cleaned['code'] = code

    # ─── دسته‌بندی ───
    cat_raw = str(raw.get('category') or '').strip()
    category = None
    if not cat_raw:
        errors.append('دسته‌بندی الزامی است')
    else:
        category = (
            Category.objects.filter(slug=cat_raw).first()
            or Category.objects.filter(name=cat_raw).first()
        )
        if not category:
            errors.append(f'دسته‌بندی «{cat_raw}» یافت نشد')
    cleaned['category'] = category

    # ─── واحد ───
    cleaned['unit'] = resolve_choice(
        raw.get('unit'), Product.UNIT_CHOICES, default='عدد',
    )

    # ─── قیمت فروش ───
    price = parse_int(raw.get('price'), default=0)
    if price is None:
        price = 0
    if price < 0:
        errors.append('قیمت فروش نمی‌تواند منفی باشد')
        price = 0
    cleaned['price'] = price

    # ─── قیمت خرید ───
    cost_price = parse_int(raw.get('cost_price'), default=0)
    if cost_price is None:
        cost_price = 0
    if cost_price < 0:
        errors.append('قیمت خرید نمی‌تواند منفی باشد')
        cost_price = 0
    cleaned['cost_price'] = cost_price

    # ─── موجودی ───
    stock = parse_int(raw.get('stock'), default=0)
    if stock is None:
        stock = 0
    cleaned['stock'] = stock

    # ─── حداقل موجودی ───
    min_stock = parse_int(raw.get('min_stock'), default=0)
    if min_stock is None:
        min_stock = 0
    if min_stock < 0:
        errors.append('حداقل موجودی نمی‌تواند منفی باشد')
        min_stock = 0
    cleaned['min_stock'] = min_stock

    # ─── توضیحات ───
    cleaned['description'] = str(raw.get('description') or '').strip() or None

    return cleaned, errors


def save_valid_products(rows, user):
    """ذخیره‌ی فقط ردیف‌های معتبر. موجودی اولیه → StockMovement"""
    created = 0
    skipped = 0
    errors = []

    for row in rows:
        if not row['is_valid']:
            skipped += 1
            continue
        try:
            data = dict(row['data'])
            initial_stock = data.pop('stock', 0)
            product = Product.objects.create(**data)

            if initial_stock and initial_stock != 0:
                product.change_stock(
                    initial_stock,
                    movement_type='in',
                    user=user,
                    reference_type='manual',
                    reference_note='ورود اولیه از Excel',
                )
            created += 1
        except Exception as e:
            skipped += 1
            errors.append(f"ردیف {row['row_num']}: {e}")

    return {'created': created, 'skipped': skipped, 'errors': errors}


def build_product_template():
    headers = list(PRODUCT_HEADER_MAP.keys())
    sample = [
        'گوشی موبایل', 'MOB-001', 'mobile', 'عدد',
        '10000000', '8000000', '10', '2', 'توضیحات نمونه',
    ]
    notes = [
        '📌 راهنمای تکمیل:',
        '• ستون‌های «نام کالا»، «کد کالا» و «دسته‌بندی» الزامی هستند.',
        '• دسته‌بندی: نام دقیق یا slug دسته (مثلاً mobile یا موبایل).',
        '• واحد: عدد / کیلوگرم / گرم / متر / لیتر / بسته / جعبه',
        '• اعداد می‌توانند با کاما یا فارسی باشند.',
        '• موجودی اولیه به‌عنوان یک StockMovement «ورود» ثبت می‌شود.',
        '• کد کالا باید یکتا باشد و در سیستم ثبت نشده باشد.',
    ]
    return build_xlsx(headers, sample_row=sample, notes=notes)