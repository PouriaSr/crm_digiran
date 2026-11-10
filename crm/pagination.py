"""Shared pagination for record lists; selectors and record line items are unaffected."""
from django.core.paginator import Paginator

PAGE_SIZE = 10


def paginate(request, records, key='page'):
    from accounts.structure_registry import scope_for_request
    from accounts.structure_service import schema
    from accounts.structure_lists import adapter,filter_records,attach_rows
    section=schema(scope_for_request(request),request) if scope_for_request(request) else None
    configured=section and hasattr(records,'model') and adapter(section,records.model) is not None
    if configured:records=filter_records(request,section,records,records.model._meta.label=='accounts.SectionRecord')
    page = Paginator(records, section.page_size if configured else PAGE_SIZE).get_page(request.GET.get(key))
    if configured:attach_rows(request,section,page)
    page.page_key = key
    return page
