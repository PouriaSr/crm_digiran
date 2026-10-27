import re
from datetime import time
from crm.duplicate_check import normalize_digits


def parse_followup_time(value):
    value = normalize_digits(value or '')
    if not re.fullmatch(r'[0-9]{2}:[0-9]{2}(?::[0-9]{2})?', value):
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None
