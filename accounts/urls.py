from django.urls import path
from django.contrib.auth import views as auth_views
from . import views, twofa_views
from .auth_views import RateLimitedLoginView

app_name = 'accounts'

urlpatterns = [
    # ورود/خروج
    path('login/', RateLimitedLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(
        next_page='accounts:login'
    ), name='logout'),
    # تغییر رمز توسط خود کاربر
    path('password-change/', views.CustomPasswordChangeView.as_view(), name='password_change'),

    # 2FA — فاز ۸.۳
    path('2fa/setup/', twofa_views.twofa_setup, name='twofa_setup'),
    path('2fa/verify/', twofa_views.twofa_verify, name='twofa_verify'),
    path('2fa/disable/', twofa_views.twofa_disable, name='twofa_disable'),
    path('2fa/recovery/', twofa_views.twofa_recovery_codes, name='twofa_recovery_codes'),
    path('2fa/recovery/regenerate/', twofa_views.twofa_regenerate_recovery, name='twofa_regenerate_recovery'),

    # مدیریت کاربران
    path('users/', views.user_list, name='user_list'),
    path('users/new/', views.user_create, name='user_create'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:pk>/password/', views.user_password, name='user_password'),
    path('users/<int:pk>/delete/', views.user_delete, name='user_delete'),
    path('users/<int:pk>/toggle/', views.user_toggle_active, name='user_toggle'),
]