from django.urls import path
from . import views

app_name = 'communications'
urlpatterns = [path('', views.center, name='center')]
