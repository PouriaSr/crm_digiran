"""Card ownership is checked on every request, independently of UI visibility."""
from accounts.permissions import get_user_role, ROLE_SALES_MANAGER


def is_card_manager(user):
    return bool(user and user.is_authenticated and (
        user.is_superuser or get_user_role(user) == ROLE_SALES_MANAGER
    ))


def card_manager_for_request(request):
    if not hasattr(request, '_is_card_manager'):
        request._is_card_manager = is_card_manager(request.user)
    return request._is_card_manager


def can_edit_card(user, customer, manager=None):
    if not user or not user.is_authenticated:
        return False
    if manager is None:
        manager = is_card_manager(user)
    return bool(manager or (customer is not None and customer.assigned_to_id == user.pk))


def can_edit_call(user, call, manager=None):
    if manager is None:
        manager = is_card_manager(user)
    return bool(manager or (call.customer_id and can_edit_card(user, call.customer, manager=False)))
