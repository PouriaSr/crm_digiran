from django import template
from customers.access import can_edit_card as check_card, can_edit_call as check_call, card_manager_for_request

register = template.Library()


@register.simple_tag(takes_context=True)
def can_edit_card(context, customer):
    request = context['request']
    return check_card(request.user, customer, card_manager_for_request(request))


@register.simple_tag(takes_context=True)
def can_edit_call(context, call):
    request = context['request']
    return check_call(request.user, call, card_manager_for_request(request))
