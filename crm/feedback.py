"""Keep redirect messages tied to the action and record that produced them."""
import json
from urllib.parse import parse_qs, urlsplit

from django.urls import Resolver404, get_script_prefix, resolve


def numeric(value):
    value = str(value or '')
    return value if value.isascii() and value.isdigit() and len(value) < 16 else ''


def record_kind(app, view):
    if app == 'customers':
        return 'customer'
    if app == 'products':
        return 'category' if view.startswith('category') else 'product'
    if app == 'ads':
        return next((name for name in ('source','platform','process') if view.startswith(name)), 'ad')
    if app == 'hr':
        return next((name for name in ('task','leave','attendance') if view.startswith(name)), 'employee')
    return {'calls':'call','sales':'invoice','accounts':'user'}.get(app, '')


class FeedbackContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        storage = getattr(request, '_messages', None)
        queued = getattr(storage, '_queued_messages', [])
        if request.method != 'POST' or not response.has_header('Location') or not queued:
            return response
        source = request.resolver_match
        location = urlsplit(response['Location'])
        prefix = get_script_prefix().rstrip('/')
        path = location.path
        if prefix and path.startswith(prefix+'/'):
            path = path[len(prefix):]
        try:
            destination = resolve(path)
        except Resolver404:
            destination = None
        context = {'source': request.path}
        reception = numeric(parse_qs(location.query).get('r', [''])[0]) or numeric(request.POST.get('reception'))
        if reception:
            context['record'] = 'reception:'+reception
        else:
            match = destination if destination and numeric(destination.kwargs.get('pk')) else source
            if match and numeric(match.kwargs.get('pk')):
                context['record'] = record_kind(match.app_name, match.url_name or '')+':'+numeric(match.kwargs['pk'])
            elif numeric(request.POST.get('customer')):
                context['record'] = 'customer:'+numeric(request.POST['customer'])
        context.update(getattr(request, 'feedback_context', {}))
        for message in queued:
            if not message.extra_tags:
                message.extra_tags = json.dumps(context, ensure_ascii=True, separators=(',', ':'))
        return response
