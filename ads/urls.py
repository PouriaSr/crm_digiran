from django.urls import path

from . import views

app_name = 'ads'

urlpatterns = [
    # تبلیغات
    path('', views.ad_list, name='list'),
    path('new/', views.ad_create, name='create'),
    path('<int:pk>/edit/', views.ad_edit, name='edit'),
    path('<int:pk>/delete/', views.ad_delete, name='delete'),

    # گزارش
    path('export/report/', views.ad_export_report, name='export_report'),

    # مدیریت (ادمین)
    path('manage/platforms/', views.platform_list, name='platform_list'),
    path('manage/platforms/<int:pk>/delete/', views.platform_delete, name='platform_delete'),
    path('manage/processes/', views.process_list, name='process_list'),
    path('manage/processes/<int:pk>/delete/', views.process_delete, name='process_delete'),
    path('manage/sources/', views.source_list, name='source_list'),
    path('manage/sources/<int:pk>/delete/', views.source_delete, name='source_delete'),

    # API
    path('api/platform/<int:pk>/processes/', views.platform_processes_api, name='platform_processes_api'),
    path('api/platform/<int:pk>/next-ad-number/', views.platform_next_ad_number_api, name='platform_next_ad_number_api'),
    path('api/process/<int:pk>/cost/', views.process_cost_api, name='process_cost_api'),
]