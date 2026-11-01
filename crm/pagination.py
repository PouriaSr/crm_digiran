"""Shared pagination for record lists; selectors and record line items are unaffected."""
from django.core.paginator import Paginator

PAGE_SIZE = 10


def paginate(request, records, key='page'):
    page = Paginator(records, PAGE_SIZE).get_page(request.GET.get(key))
    page.page_key = key
    return page
