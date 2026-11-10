from django import template
register=template.Library()


@register.filter
def interface_key(field):
    cls=field.form.__class__
    if cls.__name__=='InterfaceForm':return ''
    return f'field.{cls.__module__}.{cls.__name__}.{field.name}'


@register.simple_tag(takes_context=True)
def structure_payload(context):
    from django.utils.html import json_script
    from django.utils.safestring import mark_safe
    request=context.get('request')
    payload=getattr(request,'_structure_list_payload',{}) if request else {}
    if not payload:return ''
    return mark_safe(str(json_script(payload)).replace('<script ','<script data-structure-payload ',1))
