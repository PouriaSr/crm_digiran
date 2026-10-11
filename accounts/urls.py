from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .auth_views import RateLimitedLoginView

app_name = 'accounts'

urlpatterns = [
    # ورود/خروج — LoginView سفارشی با rate limiting (۸.۲)
    path('login/', RateLimitedLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(
        next_page='accounts:login'
    ), name='logout'),

    # مدیریت کاربران
    path('users/', views.user_list, name='user_list'),
    path('users/new/', views.user_create, name='user_create'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:pk>/password/', views.user_password, name='user_password'),
    path('users/<int:pk>/delete/', views.user_delete, name='user_delete'),
    path('users/<int:pk>/toggle/', views.user_toggle_active, name='user_toggle'),
]