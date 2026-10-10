from django.contrib import admin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'mobile', 'status', 'source',
                    'assigned_to', 'created_at')
    list_filter = ('status', 'source', 'assigned_to', 'created_at')
    search_fields = ('name', 'mobile', 'email', 'national_id')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('name', 'mobile', 'email', 'national_id', 'birth_date')
        }),
        ('وضعیت و طبقه‌بندی', {
            'fields': ('status', 'source', 'assigned_to')
        }),
        ('اطلاعات تکمیلی', {
            'fields': ('address', 'notes')
        }),
        ('زمان‌ها', {
            'fields': ('first_contact_date',),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ('created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)