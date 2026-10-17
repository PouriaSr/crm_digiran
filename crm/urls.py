from django.contrib import admin
from django.urls import path, include
from django.urls import path
from crm import views as crm_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls')),
    path('accounts/', include('accounts.urls')),
    path('customers/', include('customers.urls')),
    path('calls/', include('calls.urls')),
    path('products/', include('products.urls')),
    path('invoices/', include('sales.urls')),
    path('hr/', include('hr.urls')),
    path('audit/', include('audit.urls')),
    path('ads/', include('ads.urls')),
    path('setup/run-command/', crm_views.run_setup_command, name='run_setup_command'),

]


# ═══════════════════════════════════════════════════════════
# Error handlers — ۸.۱
# ═══════════════════════════════════════════════════════════
handler403 = 'crm.views.custom_403_view'