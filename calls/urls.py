from django.urls import path
from . import views

app_name = 'calls'

urlpatterns = [
    path('', views.call_list, name='list'),
    path('new/', views.call_create, name='create'),
    path('<int:pk>/', views.call_detail, name='detail'),
    path('<int:pk>/edit/', views.call_edit, name='edit'),
    path('<int:pk>/delete/', views.call_delete, name='delete'),
    path('<int:pk>/reassign/', views.call_reassign, name='reassign'),
]