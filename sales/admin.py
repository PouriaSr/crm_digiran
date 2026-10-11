from django.contrib import admin
from .models import Invoice, InvoiceItem, InvoiceLog


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    fields = ('product', 'quantity', 'unit_price', 'total_price')
    readonly_fields = ('total_price',)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('number', 'customer', 'status', 'total', 'issue_date', 'created_by')
    list_filter = ('status', 'payment_type', 'issue_date')
    search_fields = ('number', 'customer__name', 'customer__mobile')
    date_hierarchy = 'issue_date'
    ordering = ('-created_at',)
    inlines = [InvoiceItemInline]

    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('number', 'customer', 'status', 'payment_type')
        }),
        ('تاریخ‌ها', {
            'fields': ('issue_date', 'due_date')
        }),
        ('مبالغ', {
            'fields': ('subtotal', 'discount', 'tax_percent', 'tax_amount', 'total')
        }),
        ('توضیحات', {
            'fields': ('notes',)
        }),
    )
    readonly_fields = ('number', 'subtotal', 'tax_amount', 'total', 'created_at', 'updated_at')


@admin.register(InvoiceLog)
class InvoiceLogAdmin(admin.ModelAdmin):
    """لاگ‌ها فقط خواندنی — برای شفافیت و audit"""

    list_display = ('created_at', 'invoice', 'action', 'user', 'description_preview')
    list_filter = ('action', 'created_at')
    search_fields = ('invoice__number', 'description', 'user__username')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    readonly_fields = (
        'invoice', 'user', 'action', 'field_name',
        'old_value', 'new_value', 'description', 'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # فقط سوپریوزر
        return request.user.is_superuser

    @admin.display(description='توضیحات')
    def description_preview(self, obj):
        return obj.description[:80] + ('...' if len(obj.description) > 80 else '')