from django.contrib import admin
from django.urls import path, include


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
]


# ═══════════════════════════════════════════════════════════
# Error handlers — ۸.۱
# ═══════════════════════════════════════════════════════════
handler403 = 'crm.views.custom_403_view'