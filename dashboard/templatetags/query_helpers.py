"""
تگ‌های کمکی برای ساخت query string با حفظ پارامترهای فعلی.
استفاده در pagination و لینک‌های حفظ فیلتر (۷.۶).
"""
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    """
    ساخت query string با پارامترهای فعلی request.GET
    و override/حذف پارامترهای داده‌شده.

    مثال:
        {% querystring page=2 %}                → همه‌ی فیلترها + page=2
        {% querystring page=None %}             → حذف page
        {% querystring status='paid' %}         → override status
    """
    request = context.get('request')
    if not request:
        return ''

    params = request.GET.copy()
    for key, value in kwargs.items():
        if value is None or value == '':
            params.pop(key, None)
        else:
            params[key] = value

    return params.urlencode()