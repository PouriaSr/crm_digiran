from django.urls import path
from django.contrib.auth import views as auth_views
from . import views, twofa_views, interface_views, structure_views, behavior_views
from .auth_views import RateLimitedLoginView

app_name = 'accounts'

urlpatterns = [
    path('settings/sections/<slug:section_key>/reference-options/', behavior_views.reference_options, name='behavior_reference_options'),
    path('settings/sections/<slug:section_key>/inputs/<str:field_name>/', behavior_views.inspector, name='behavior_inspector'),
    path('settings/sections/<slug:section_key>/inputs/<str:field_name>/options/new/', behavior_views.option_edit, name='behavior_option_create'),
    path('settings/sections/<slug:section_key>/inputs/<str:field_name>/options/<int:pk>/', behavior_views.option_edit, name='behavior_option_edit'),
    path('settings/sections/<slug:section_key>/rules/new/', behavior_views.rule_edit, name='behavior_rule_create'),
    path('settings/sections/<slug:section_key>/rules/<int:pk>/', behavior_views.rule_edit, name='behavior_rule_edit'),
    path('settings/sections/<slug:section_key>/behaviors/<str:kind>/<int:pk>/archive/', behavior_views.archive, name='behavior_archive'),
    path('settings/sections/new/', structure_views.section_edit, name='structure_create'),
    path('settings/sections/<slug:section_key>/apply-existing/', structure_views.apply_existing, name='structure_apply_existing'),
    path('settings/sections/<slug:section_key>/', structure_views.section_edit, name='structure_section'),
    path('settings/sections/<slug:section_key>/<str:kind>/new/', structure_views.element_edit, name='structure_element_create'),
    path('settings/sections/<slug:section_key>/<str:kind>/<int:pk>/', structure_views.element_edit, name='structure_element_edit'),
    path('settings/sections/<slug:section_key>/<str:kind>/<int:pk>/archive/', structure_views.element_archive, name='structure_element_archive'),
    path('sections/<slug:section_key>/data/', structure_views.data_list, name='structure_data'),
    path('sections/<slug:section_key>/new/', structure_views.data_edit, name='structure_record_create'),
    path('sections/<slug:section_key>/record/<int:pk>/archive/', structure_views.record_archive, name='structure_record_archive'),
    path('sections/<slug:section_key>/record/<int:pk>/', structure_views.data_edit, name='structure_record'),
    path('sections/<slug:section_key>/native/<int:native_pk>/', structure_views.data_edit, name='structure_native_record'),
    path('settings/', interface_views.settings, name='interface_settings'),
    path('settings/new/', interface_views.edit, name='interface_create'),
    path('settings/edit/<str:key>/', interface_views.edit, name='interface_edit'),
    path('settings/reset/<str:key>/', interface_views.reset, name='interface_reset'),
    path('pages/<int:pk>/', interface_views.page, name='interface_page'),
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