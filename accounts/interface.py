"""UI configuration never grants permission to the underlying operation."""
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote,urlsplit
import re
from django.urls import reverse, get_script_prefix
from .permissions import get_user_role, has_permission


@lru_cache(maxsize=1)
def catalog():
    return json.loads(Path(__file__).with_name('ui_catalog.json').read_text(encoding='utf-8'))


def settings_destination(value):
    path=unquote(urlsplit(value or '').path)
    return bool(re.search(r'(?:^|/)accounts/settings(?:/|$)',path))


def permitted(user, component):
    return ((not settings_destination(component.url) or has_permission(user,'system.configure')) and component.enabled and (not component.roles or get_user_role(user) in component.roles)
            and (not component.permission or has_permission(user, component.permission)))


def internal_url(value):
    prefix=get_script_prefix().rstrip('/')
    return prefix+value if prefix and not (value==prefix or value.startswith(prefix+'/')) else value


def component_settings(request):
    from .models import InterfaceComponent
    if not hasattr(request,'_interface_components'):request._interface_components=list(InterfaceComponent.objects.all())
    return request._interface_components


def interface_context(request):
    if not request.user.is_authenticated:
        return {}
    from .models import InterfaceComponent
    settings = component_settings(request)
    overrides = []
    links = []
    for item in settings:
        visible = permitted(request.user, item)
        if item.behavior.get('action_kind')=='navigate' and settings_destination(item.behavior.get('destination')):
            visible=visible and has_permission(request.user,'system.configure')
        if item.custom:
            from .structure_registry import scope_for_request
            if visible and (not item.scope_path or request.path_info == item.scope_path) and (not item.scope_key or item.scope_key==scope_for_request(request)):
                links.append({'key': item.key, 'label': item.label, 'kind': item.kind,
                              'url': internal_url(item.url) if item.url else reverse('accounts:interface_page', args=[item.pk])})
        elif item.key in catalog():
            overrides.append({'key': item.key, 'label': item.label if catalog()[item.key].get('label_mutable',True) and item.label!=catalog()[item.key]['label'] else '', 'order_changed':item.position!=catalog()[item.key]['position'], 'visible': visible, 'position': item.position,
                              'kind': item.kind,'behavior':{**item.behavior,**({'destination':internal_url(item.behavior['destination'])} if item.behavior.get('destination') else {})}})
    return {'interface_overrides': overrides, 'interface_links': links}
