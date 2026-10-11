from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    # کالاها
    path('', views.product_list, name='list'),
    path('new/', views.product_create, name='create'),
    path('<int:pk>/', views.product_detail, name='detail'),
    path('<int:pk>/edit/', views.product_edit, name='edit'),
    path('<int:pk>/delete/', views.product_delete, name='delete'),
    path('<int:pk>/restore/', views.product_restore, name='restore'),

    # دسته‌بندی‌ها
    path('categories/', views.category_list, name='category_list'),
    path('categories/new/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),

    # ورود از Excel (۷.۸)
    path('excel/', views.product_excel_import, name='excel_import'),
    path('excel/template/', views.product_excel_template, name='excel_template'),
    path('excel/<uuid:token>/', views.product_excel_preview, name='excel_preview'),
]