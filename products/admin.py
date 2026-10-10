from django.contrib import admin, messages
from django.utils import timezone
from .models import Product, StockMovement, Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('icon', 'name', 'slug', 'order', 'is_active', 'products_count', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'slug', 'description')
    ordering = ('order', 'name')
    list_editable = ('order', 'is_active')

    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('name', 'slug', 'icon', 'description')
        }),
        ('تنظیمات', {
            'fields': ('order', 'is_active')
        }),
    )

    def products_count(self, obj):
        return obj.products_count
    products_count.short_description = 'تعداد کالا'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'category', 'price', 'stock',
                    'is_active', 'is_deleted', 'created_at')
    list_filter = ('category', 'unit', 'is_active', 'is_deleted')
    search_fields = ('name', 'code', 'description')
    ordering = ('-created_at',)
    autocomplete_fields = ['category']

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
        ('وضعیت حذف', {
            'fields': ('is_deleted', 'deleted_at'),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')

    actions = ['soft_delete_selected', 'restore_selected', 'hard_delete_selected']

    def get_queryset(self, request):
        return Product.all_objects.all()

    @admin.action(description='حذف نرم (Soft Delete)')
    def soft_delete_selected(self, request, queryset):
        count = 0
        for product in queryset.filter(is_deleted=False):
            product.delete()
            count += 1
        self.message_user(request, f'{count} کالا حذف نرم شد.', messages.SUCCESS)

    @admin.action(description='بازگرداندن')
    def restore_selected(self, request, queryset):
        count = 0
        for product in queryset.filter(is_deleted=True):
            product.restore()
            count += 1
        self.message_user(request, f'{count} کالا بازگردانده شد.', messages.SUCCESS)

    @admin.action(description='حذف کامل (خطرناک!)')
    def hard_delete_selected(self, request, queryset):
        try:
            count = 0
            for product in queryset:
                product.hard_delete()
                count += 1
            self.message_user(request, f'{count} کالا کامل حذف شد.', messages.WARNING)
        except Exception as e:
            self.message_user(request, f'خطا: {e}', messages.ERROR)


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
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return StockMovement.objects.select_related('product', 'created_by')