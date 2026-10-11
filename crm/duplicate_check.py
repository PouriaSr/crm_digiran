"""
سیستم جامع تشخیص تکراری — Exact (بلاک) + Similar (هشدار)

قواعد:
- Exact match در فیلدهای کلیدی (mobile, code, ...) → ValidationError (block)
- Similar match در فیلدهای متنی (name, ...) → duplicate_warnings (soft)
"""
import re
from difflib import SequenceMatcher


# ═══════════════════════════════════════════════════
# ثابت‌ها
# ═══════════════════════════════════════════════════
DEFAULT_SIMILARITY_THRESHOLD = 0.85
MIN_LENGTH_FOR_SIMILARITY = 3
MAX_ITER_FOR_SIMILARITY = 5000  # سقف برای امنیت performance


# ═══════════════════════════════════════════════════
# نرمال‌سازی
# ═══════════════════════════════════════════════════
_ARABIC_TO_PERSIAN = {
    'ي': 'ی', 'ك': 'ک', 'ة': 'ه', 'ۀ': 'ه',
    'ؤ': 'و', 'إ': 'ا', 'أ': 'ا',
}
_FA_TO_EN_DIGITS = {
    '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
    '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
    '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
}


def normalize_text(value, lower=True):
    """نرمال‌سازی متن برای مقایسه (ی/ک عربی، ZWNJ، فاصله)"""
    if value is None:
        return ''
    s = str(value).strip()
    for ar, fa in _ARABIC_TO_PERSIAN.items():
        s = s.replace(ar, fa)
    s = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', s)
    s = re.sub(r'\s+', ' ', s)
    if lower:
        s = s.lower()
    return s.strip()


def normalize_phone(value):
    """فقط ارقام — برای موبایل/تلفن"""
    if not value:
        return ''
    s = str(value)
    for fa, en in _FA_TO_EN_DIGITS.items():
        s = s.replace(fa, en)
    return re.sub(r'\D', '', s)


def normalize_digits(value):
    """تبدیل ارقام فارسی/عربی به انگلیسی"""
    if not value:
        return ''
    s = str(value)
    for fa, en in _FA_TO_EN_DIGITS.items():
        s = s.replace(fa, en)
    return s.strip()


def normalize_code(value):
    """نرمال‌سازی کد (SKU، slug)"""
    if not value:
        return ''
    s = normalize_digits(value)
    return re.sub(r'\s+', '', s).lower()


def normalize_email(value):
    """نرمال‌سازی ایمیل"""
    if not value:
        return ''
    return normalize_text(value, lower=True)


# ═══════════════════════════════════════════════════
# مشابهت
# ═══════════════════════════════════════════════════
def similarity_ratio(a, b):
    """نسبت مشابهت (0..1)"""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def is_similar(a, b, threshold=DEFAULT_SIMILARITY_THRESHOLD):
    return similarity_ratio(a, b) >= threshold


# ═══════════════════════════════════════════════════
# جستجو در دیتابیس
# ═══════════════════════════════════════════════════
def _qs_for_field(model, field_name, exclude_pk=None):
    qs = model.objects.all()
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.only('pk', field_name)


def find_exact_match(model, field_name, value, normalize_func,
                     exclude_pk=None, extra_filter=None):
    """پیدا کردن رکوردی که مقدار نرمال‌شده‌اش دقیقاً برابر باشه."""
    if not value:
        return None
    target = normalize_func(value)
    if not target:
        return None

    qs = _qs_for_field(model, field_name, exclude_pk)
    if extra_filter:
        qs = qs.filter(**extra_filter)

    # بهینه: فیلتر مستقیم DB اگه مقدار خام ذخیره شده
    direct = qs.filter(**{field_name: value}).first()
    if direct:
        return direct

    # scan محدود
    for i, obj in enumerate(qs):
        if i >= MAX_ITER_FOR_SIMILARITY:
            break
        raw = getattr(obj, field_name, '')
        if normalize_func(raw) == target:
            return obj
    return None


def find_similar_matches(model, field_name, value, normalize_func,
                         threshold=DEFAULT_SIMILARITY_THRESHOLD,
                         exclude_pk=None, max_results=5,
                         extra_filter=None):
    """پیدا کردن رکوردهای مشابه (نه دقیقاً یکسان)."""
    if not value:
        return []
    target = normalize_func(value)
    if not target or len(target) < MIN_LENGTH_FOR_SIMILARITY:
        return []

    qs = _qs_for_field(model, field_name, exclude_pk)
    if extra_filter:
        qs = qs.filter(**extra_filter)

    results = []
    for i, obj in enumerate(qs):
        if i >= MAX_ITER_FOR_SIMILARITY:
            break
        raw = getattr(obj, field_name, '')
        normalized = normalize_func(raw)
        if not normalized or len(normalized) < MIN_LENGTH_FOR_SIMILARITY:
            continue
        ratio = similarity_ratio(target, normalized)
        if ratio >= threshold:
            results.append((obj, ratio))

    results.sort(key=lambda x: -x[1])
    return results[:max_results]


def find_similar_fullname(model, value, normalize_func,
                          threshold=DEFAULT_SIMILARITY_THRESHOLD,
                          exclude_pk=None, max_results=5,
                          first_field='first_name', last_field='last_name'):
    """جستجوی مشابهت روی ترکیب first_name + last_name"""
    if not value:
        return []
    target = normalize_func(value)
    if not target or len(target) < MIN_LENGTH_FOR_SIMILARITY:
        return []

    qs = model.objects.all()
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    qs = qs.only('pk', first_field, last_field)

    results = []
    for i, obj in enumerate(qs):
        if i >= MAX_ITER_FOR_SIMILARITY:
            break
        first = getattr(obj, first_field, '') or ''
        last = getattr(obj, last_field, '') or ''
        combined = normalize_func(f'{first} {last}')
        if not combined or len(combined) < MIN_LENGTH_FOR_SIMILARITY:
            continue
        ratio = similarity_ratio(target, combined)
        if ratio >= threshold:
            results.append((obj, ratio))

    results.sort(key=lambda x: -x[1])
    return results[:max_results]


# ═══════════════════════════════════════════════════
# نمایش هشدارها (view helper)
# ═══════════════════════════════════════════════════
def show_duplicate_warnings(request, form):
    """
    نمایش هشدارهای مشابهت بعد از save موفق.
    warning dict keys: field, label, value, match, ratio
    """
    from django.contrib import messages

    warnings = getattr(form, 'duplicate_warnings', [])
    if not warnings:
        return

    seen = set()
    for w in warnings:
        key = (w['field'], w['match'].pk)
        if key in seen:
            continue
        seen.add(key)

        messages.warning(
            request,
            f"⚠️ هشدار: {w['label']} مشابه با «{w['match']}» "
            f"({w['ratio']}٪ تطابق) — در صورت نیاز، بررسی و ادغام کنید."
        )