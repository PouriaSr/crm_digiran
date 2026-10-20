from django.urls import path
from . import views, hub_views

app_name = 'customers'

urlpatterns = [
    # Redirect old list to new Hub
    path('', views.customer_list, name='list'),
    
    # New Hub Routes
    path('hub/', hub_views.customer_hub, name='hub'),
    path('hub/call/', hub_views.hub_submit_call, name='hub_submit_call'),
    path('hub/visit/', hub_views.hub_submit_visit, name='hub_submit_visit'),
    path('hub/api/check/', hub_views.hub_check_customer, name='hub_check_api'),

    # Original CRUD Routes (Crucial for detail.html and forms to work)
    path('new/', views.customer_create, name='create'),
    path('<int:pk>/', views.customer_detail, name='detail'),
    path('<int:pk>/edit/', views.customer_edit, name='edit'),
    path('<int:pk>/reassign/', hub_views.customer_reassign, name='reassign'),
    path('<int:pk>/deactivate/', views.customer_deactivate, name='deactivate'),
    path('<int:pk>/restore/', views.customer_restore, name='restore'),
    path('inactive/', views.customer_inactive_list, name='inactive_list'),

    # Notes
    path('<int:pk>/notes/add/', views.note_create, name='note_create'),
    path('<int:pk>/notes/<int:note_pk>/edit/', views.note_edit, name='note_edit'),
    path('<int:pk>/notes/<int:note_pk>/delete/', views.note_delete, name='note_delete'),
    path('<int:pk>/notes/<int:note_pk>/pin/', views.note_toggle_pin, name='note_toggle_pin'),

    # Excel
    path('excel/', views.customer_excel_import, name='excel_import'),
    path('excel/template/', views.customer_excel_template, name='excel_template'),
    path('excel/<uuid:token>/', views.customer_excel_preview, name='excel_preview'),
]
