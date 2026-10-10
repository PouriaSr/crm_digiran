from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()

# ═══ نقشه اعداد فارسی ═══
EN_TO_FA = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


def _to_persian_digits(value):
    """تبدیل اعداد انگلیسی به فارسی"""
    return str(value).translate(EN_TO_FA)


def _add_commas(value):
    """افزودن جداکننده هزارگان (۳ رقم ۳ رقم)"""
    try:
        # اگه اعشار داره
        s = str(value)
        if '.' in s:
            int_part, dec_part = s.split('.')
        else:
            int_part, dec_part = s, None

        # حذف کاراکترهای غیرعددی
        negative = False
        if int_part.startswith('-'):
            negative = True
            int_part = int_part[1:]

        int_part = int_part.replace(',', '').strip()

        if not int_part.isdigit():
            return str(value)

        # افزودن کاما
        result = '{:,}'.format(int(int_part))

        if negative:
            result = '-' + result

        if dec_part:
            result = result + '.' + dec_part

        return result
    except (ValueError, TypeError):
        return str(value)


@register.filter(name='fa_num')
def fa_num(value):
    """تبدیل عدد به فارسی با جداکننده هزارگان"""
    if value is None or value == '':
        return '۰'

    # اگه عدد است، جداکننده بذار
    try:
        if isinstance(value, (int, float, Decimal)):
            formatted = _add_commas(value)
            return _to_persian_digits(formatted)
        # اگه رشته است، اول کاما بذار (اگه عددی بود)، بعد فارسی کن
        return _to_persian_digits(_add_commas(value))
    except Exception:
        return _to_persian_digits(str(value))


@register.filter(name='fa_price')
def fa_price(value):
    """قیمت به فارسی + تومان"""
    if value is None:
        return '۰ تومان'
    return fa_num(value) + ' تومان'


@register.filter(name='fa_digits')
def fa_digits(value):
    """فقط تبدیل اعداد به فارسی (بدون کاما)"""
    if value is None or value == '':
        return ''
    return _to_persian_digits(str(value))


@register.filter(name='fa_date')
def fa_date(value):
    """تبدیل تاریخ به فارسی (اعداد رو فارسی می‌کنه، / رو نگه می‌داره)"""
    if not value:
        return ''
    return _to_persian_digits(str(value))