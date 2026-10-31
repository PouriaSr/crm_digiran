from django import template
from decimal import Decimal
import jdatetime
from crm.numerals import persian_digits, normalize_input

register = template.Library()


@register.simple_tag(takes_context=True)
def workflow_page_url(context, key, number, tab):
    query = context['request'].GET.copy()
    query[key] = number
    query['tab'] = tab
    return '?' + query.urlencode()

def _to_persian_digits(value):
    """تبدیل اعداد انگلیسی به فارسی"""
    return persian_digits(value)


def _add_commas(value):
    """افزودن جداکننده هزارگان (۳ رقم ۳ رقم)"""
    try:
        s = normalize_input(value)
        if '.' in s:
            int_part, dec_part = s.split('.')
        else:
            int_part, dec_part = s, None

        negative = False
        if int_part.startswith('-'):
            negative = True
            int_part = int_part[1:]

        int_part = int_part.replace(',', '').strip()

        if not int_part.isdigit():
            return str(value)

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

    try:
        if isinstance(value, (int, float, Decimal)):
            formatted = _add_commas(value)
            return _to_persian_digits(formatted)
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


@register.filter(name='jdate', expects_localtime=True)
def jdate(value, arg=None):
    """
    تبدیل تاریخ میلادی به شمسی با پشتیبانی از فرمت‌های جنگو (Y, m, d, H, i)
    """
    if not value:
        return ''

    if not arg:
        arg = "Y/m/d"

    # تبدیل فرمت جنگو به فرمت پایتون (strftime)
    # مثلا Y/m/d H:i میشه %Y/%m/%d %H:%M
    fmt = str(arg)
    fmt = fmt.replace('Y', '%Y')
    fmt = fmt.replace('y', '%y')
    fmt = fmt.replace('m', '%m')
    fmt = fmt.replace('d', '%d')
    fmt = fmt.replace('H', '%H')
    fmt = fmt.replace('i', '%M')  # در جنگو i دقیقه است، در پایتون M
    fmt = fmt.replace('s', '%S')

    if hasattr(value, 'year'):
        try:
            if hasattr(value, 'hour'):  # datetime
                j_val = jdatetime.datetime.fromgregorian(datetime=value)
            else:  # date
                j_val = jdatetime.date.fromgregorian(date=value)
            val_str = j_val.strftime(fmt)
        except Exception:
            # در صورت خطا، تاریخ میلادی را با همان فرمت نشان بده
            val_str = value.strftime(fmt)
    else:
        val_str = str(value)

    return _to_persian_digits(val_str)
