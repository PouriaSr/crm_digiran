from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    path('', views.customer_list, name='list'),
    path('new/', views.customer_create, name='create'),
    path('<int:pk>/', views.customer_detail, name='detail'),
    path('<int:pk>/edit/', views.customer_edit, name='edit'),
    path('<int:pk>/deactivate/', views.customer_deactivate, name='deactivate'),
    path('<int:pk>/restore/', views.customer_restore, name='restore'),
    path('inactive/', views.customer_inactive_list, name='inactive_list'),

    # یادداشت‌ها
    path('<int:pk>/notes/add/', views.note_create, name='note_create'),
    path('<int:pk>/notes/<int:note_pk>/edit/', views.note_edit, name='note_edit'),
    path('<int:pk>/notes/<int:note_pk>/delete/', views.note_delete, name='note_delete'),
    path('<int:pk>/notes/<int:note_pk>/pin/', views.note_toggle_pin, name='note_toggle_pin'),

    # ورود از Excel (۷.۸)
    path('excel/', views.customer_excel_import, name='excel_import'),
    path('excel/template/', views.customer_excel_template, name='excel_template'),
    path('excel/<uuid:token>/', views.customer_excel_preview, name='excel_preview'),
]