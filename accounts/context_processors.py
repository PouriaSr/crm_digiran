from .permissions import (
    get_user_permissions,
    get_user_role,
    get_user_role_display,
    ROLE_ADMIN,
    ROLE_SALES_MANAGER,
    ROLE_SALES,
    ROLE_SUPPORT,
    ROLE_ACCOUNTANT,
    ROLE_OPERATOR,
)
from .notifications import get_notifications # ⭐ اضافه شد

def permissions_context(request):
    user = request.user

    if not user.is_authenticated:
        return {
            'user_permissions': set(),
            'user_role': None,
            'user_role_display': '-',
            'is_admin': False,
            'is_sales_manager': False,
            'is_sales': False,
            'is_support': False,
            'is_accountant': False,
            'is_operator': False,
            'notifications': [],
            'notifications_count': 0,
        }

    role = get_user_role(user)
    notifications = get_notifications(user)

    return {
        'user_permissions': get_user_permissions(user),
        'user_role': role,
        'user_role_display': get_user_role_display(user),
        'is_admin': user.is_superuser or role == ROLE_ADMIN,
        'is_sales_manager': role == ROLE_SALES_MANAGER,
        'is_sales': role == ROLE_SALES,
        'is_support': role == ROLE_SUPPORT,
        'is_accountant': role == ROLE_ACCOUNTANT,
        'is_operator': role == ROLE_OPERATOR,
        'notifications': notifications, # ⭐ اضافه شد
        'notifications_count': len(notifications), # ⭐ اضافه شد
    }