from django import template
register=template.Library()


@register.filter
def interface_key(field):
    cls=field.form.__class__
    if cls.__name__=='InterfaceForm':return ''
    return f'field.{cls.__module__}.{cls.__name__}.{field.name}'
