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


@register.simple_tag
def behavior_payload(form):
    from django.utils.html import json_script
    from django.utils.safestring import mark_safe
    payload=getattr(form,'structure_behavior_payload',None)
    if not payload or not (payload.get('rules') or payload.get('option_maps') or payload.get('replace')):return ''
    return mark_safe(str(json_script(payload)).replace('<script ','<script data-form-behavior ',1))


@register.simple_tag(takes_context=True)
def behavior_labels(context,section_key,subject):
    from accounts.structure_service import schema,can_access,native_visible
    from django.contrib.contenttypes.models import ContentType
    request=context.get('request')
    if not request or not subject:return []
    section=schema(section_key,request)
    if not section or not can_access(request.user,section) or not native_visible(request.user,section,subject):return []
    record=section.records.filter(content_type=ContentType.objects.get_for_model(subject),object_id=subject.pk).only('data').first()
    return record.data.get('_behavior_tags',[]) if record else []


@register.simple_tag
def behavior_record_labels(record):
    return record.data.get('_behavior_tags',[]) if record else []
