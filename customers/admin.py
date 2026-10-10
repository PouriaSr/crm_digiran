from django.contrib import admin
from .models import Customer, CustomerNote


class CustomerNoteInline(admin.TabularInline):
    model = CustomerNote
    extra = 0
    fields = ('text', 'is_pinned', 'created_by', 'created_at')
    readonly_fields = ('created_by', 'created_at')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'mobile', 'status', 'source',
                    'assigned_to', 'created_at')
    list_filter = ('status', 'source', 'assigned_to', 'created_at')
    search_fields = ('name', 'mobile', 'email', 'national_id')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    inlines = [CustomerNoteInline]

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


@admin.register(CustomerNote)
class CustomerNoteAdmin(admin.ModelAdmin):
    list_display = ('customer', 'author_display', 'text_preview',
                    'is_pinned', 'created_at')
    list_filter = ('is_pinned', 'created_at')
    search_fields = ('customer__name', 'text')
    date_hierarchy = 'created_at'
    ordering = ('-is_pinned', '-created_at')
    autocomplete_fields = ['customer']
    readonly_fields = ('created_at', 'updated_at', 'created_by')

    def author_display(self, obj):
        return obj.author_name
    author_display.short_description = 'نویسنده'

    def text_preview(self, obj):
        return obj.text[:60] + ('...' if len(obj.text) > 60 else '')
    text_preview.short_description = 'متن'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)