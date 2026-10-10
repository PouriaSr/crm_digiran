from django.contrib import admin
from .models import Invoice, InvoiceItem


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