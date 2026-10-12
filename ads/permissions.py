"""
دسترسی‌های اپ تبلیغات — یکپارچه با RBAC مرکزی
"""
from accounts.permissions import (
    ROLE_ADS_MANAGER,
    has_permission,
    has_role,
)


def is_ads_manager(user):
    """مسئول تبلیغات یا ادمین"""
    return has_role(user, ROLE_ADS_MANAGER)


def is_admin_only(user):
    """فقط ادمین"""
    return user.is_authenticated and user.is_superuser


def can_view_ad(user, ad):
    """ادمین همه، مسئول تبلیغات فقط رکوردهای خودش"""
    if user.is_superuser:
        return True
    if has_role(user, ROLE_ADS_MANAGER):
        return ad.created_by_id == user.id
    return False


def can_manage_definitions(user):
    """آیا می‌تواند عنوان/فرآیند/منبع تعریف کند؟"""
    return has_permission(user, 'ads.manage_defs')