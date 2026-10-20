from django.urls import path
from django.shortcuts import redirect
from . import views, hub_views

app_name = 'customers'
def to_hub(request): return redirect('/customers/hub/?tab=info')
def to_call(request): return redirect('/customers/hub/?tab=call')
def to_visit(request): return redirect('/customers/hub/?tab=visit')

urlpatterns = [
    path('', to_hub),
    path('hub/', hub_views.customer_hub, name='hub'),
    path('hub/call/', hub_views.hub_submit_call, name='hub_submit_call'),
    path('hub/visit/', hub_views.hub_submit_visit, name='hub_submit_visit'),
    path('hub/api/check/', hub_views.hub_check_customer, name='hub_check_api'),
    # Keep detail/create/edit intact
    path('new/', views.customer_create, name='create'),
    path('<int:pk>/', views.customer_detail, name='detail'),
    path('<int:pk>/edit/', views.customer_edit, name='edit'),
]
    