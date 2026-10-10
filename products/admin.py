from django.contrib import admin
from .models import Product, StockMovement


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'category', 'price', 'stock', 'is_active', 'created_at')
    list_filter = ('category', 'unit', 'is_active')
    search_fields = ('name', 'code', 'description')
    ordering = ('-created_at',)

    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('name', 'code', 'category', 'unit', 'is_active')
        }),
        ('قیمت‌ها', {
            'fields': ('price', 'cost_price')
        }),
        ('موجودی', {
            'fields': ('stock', 'min_stock')
        }),
        ('توضیحات', {
            'fields': ('description',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'product', 'movement_type', 'quantity',
                    'stock_before', 'stock_after', 'reference_type', 'created_by')
    list_filter = ('movement_type', 'reference_type', 'created_at')
    search_fields = ('product__name', 'product__code', 'reference_note', 'note')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    readonly_fields = ('product', 'movement_type', 'quantity', 'stock_before',
                       'stock_after', 'reference_type', 'reference_id',
                       'reference_note', 'note', 'created_by', 'created_at')

    def has_add_permission(self, request):
        return False  # فقط از طریق کد ساخته می‌شود

    def has_delete_permission(self, request, obj=None):
        return False  # تاریخچه حذف نمی‌شود