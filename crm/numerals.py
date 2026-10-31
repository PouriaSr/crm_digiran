"""Canonical digits for business inputs; never rewrite opaque credentials."""
import re

ASCII_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
PERSIAN_DIGITS = str.maketrans('0123456789٠١٢٣٤٥٦٧٨٩', '۰۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹')
_OPAQUE_PARTS = {
    'password', 'password1', 'password2', 'token', 'secret', 'csrfmiddlewaretoken',
    'key', 'signature', 'username', 'email', 'url', 'uri', 'next', 'redirect',
    'redirectto', 'returnto', 'session', 'uidb64', 'credential',
}
_NUMBER = re.compile(r'^[+-]?(?:\d+|\d{1,3}(?:[,٬]\d{3})+)(?:[.٫]\d+)?$')


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
        value = value.replace('٬', '').replace(',', '').replace('٫', '.')
    return value


def digit_contains(field, query):
    """Search existing mixed-script records without rewriting stored business data.

    Ordinary text searches keep their usual SQL. Digit searches normalize only
    the compared column; surrounding ownership/permission filters are unchanged.
    """
    from django.db.models import F, Q, TextField, Value
    from django.db.models.functions import Replace
    from django.db.models.lookups import IContains

    query = ascii_digits(query)
    if not re.search('[0-9]', query):
        return Q(**{field + '__icontains': query})
    expression = F(field)
    for source, target in zip('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789'):
        expression = Replace(expression, Value(source), Value(target), output_field=TextField())
    return Q(IContains(expression, Value(query)))
