from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('search/', views.global_search, name='search'),
    path('export/excel/', views.export_excel, name='export_excel'),
]