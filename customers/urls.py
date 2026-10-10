from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    path('', views.customer_list, name='list'),
    path('new/', views.customer_create, name='create'),
    path('<int:pk>/', views.customer_detail, name='detail'),
    path('<int:pk>/edit/', views.customer_edit, name='edit'),

    # یادداشت‌ها
    path('<int:pk>/notes/add/', views.note_create, name='note_create'),
    path('<int:pk>/notes/<int:note_pk>/edit/', views.note_edit, name='note_edit'),
    path('<int:pk>/notes/<int:note_pk>/delete/', views.note_delete, name='note_delete'),
    path('<int:pk>/notes/<int:note_pk>/pin/', views.note_toggle_pin, name='note_toggle_pin'),
]