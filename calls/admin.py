from django.contrib import admin
from .models import Call


@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = (
        'caller_name', 'call_number', 'call_type', 'status',
        'purpose', 'customer', 'called_by', 'call_date'
    )
    list_filter = (
        'call_type', 'status', 'purpose', 'called_by',
        'call_date', 'is_followed_up'
    )
    search_fields = ('caller_name', 'call_number', 'notes')
    date_hierarchy = 'call_date'
    ordering = ('-call_date',)
    autocomplete_fields = ['customer']

    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('caller_name', 'call_number', 'customer')
        }),
        ('نوع و وضعیت', {
            'fields': ('call_type', 'status', 'purpose')
        }),
        ('زمان', {
            'fields': ('call_date', 'duration')
        }),
        ('پیگیری', {
            'fields': ('follow_up_date', 'is_followed_up')
        }),
        ('توضیحات', {
            'fields': ('notes',)
        }),
        ('مسئول', {
            'fields': ('called_by',),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ('created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
            if not obj.called_by:
                obj.called_by = request.user
        super().save_model(request, obj, form, change)