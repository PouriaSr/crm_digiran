"""Canonical digits for business inputs; never rewrite opaque credentials."""
import re
from .unicode_digits import DIGIT_GLYPHS

ASCII_DIGITS = {ord(char): str(digit) for digit, glyphs in enumerate(DIGIT_GLYPHS) for char in glyphs}
PERSIAN_DIGITS = {ord(char): '۰۱۲۳۴۵۶۷۸۹'[digit] for digit, glyphs in enumerate(DIGIT_GLYPHS) for char in glyphs}
_OPAQUE_PARTS = {
    'password', 'password1', 'password2', 'token', 'secret', 'csrfmiddlewaretoken',
    'key', 'signature', 'username', 'email', 'url', 'uri', 'next', 'redirect',
    'redirectto', 'returnto', 'session', 'uidb64', 'credential',
}
_NUMBER = re.compile(r'^[+\-＋－−]?(?:\d+|\d{1,3}(?:[,٬，]\d{3})+)(?:[.٫．]\d+)?$')


def preserve_field(name):
    parts = set(re.split(r'[^a-z0-9]+', str(name).lower()))
    return bool(parts & _OPAQUE_PARTS) or any(
        word in str(name).lower() for word in ('password', 'token', 'secret', 'credential')
    )


def ascii_digits(value):
    return str(value).translate(ASCII_DIGITS)


def persian_digits(value):
    return str(value).translate(PERSIAN_DIGITS)


def normalize_input(value):
    """Translate digits without losing leading zeroes or punctuation in prose/dates."""
    value = ascii_digits(value)
    if _NUMBER.fullmatch(value.strip()):
        # Only numeric values: leave commas in prose and date separators intact.
        value = value.translate(str.maketrans({'٬': '', ',': '', '，': '', '٫': '.', '．': '.', '＋': '+', '－': '-', '−': '-'}))
    elif re.fullmatch(r'\s*(?:\d{1,4}[/／.．\-－]\d{1,2}[/／.．\-－]\d{1,4}(?:[ T]\d{1,2}[:：﹕]\d{2}(?:[:：﹕]\d{2})?)?|\d{1,2}[:：﹕]\d{2}(?:[:：﹕]\d{2})?)\s*', value):
        value = value.translate(str.maketrans({'／': '/', '．': '.', '－': '-', '：': ':', '﹕': ':'}))
    return value


def digit_contains(field, query):
    """Search existing mixed-script records without rewriting stored business data.

    Ordinary text searches keep their usual SQL. Digit searches normalize only
    the compared column; surrounding ownership/permission filters are unchanged.
    """
    from django.db.models import Q

    query = ascii_digits(query)
    if not re.search('[0-9]', query):
        return Q(**{field + '__icontains': query})
    # A literal pattern avoids hundreds of nested SQL REPLACE calls, and also
    # finds pre-existing records containing digits from different keyboards.
    pattern = ''.join('[' + DIGIT_GLYPHS[int(char)] + ']' if char in '0123456789' else re.escape(char) for char in query)
    return Q(**{field + '__iregex': pattern})
