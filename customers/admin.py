from django.contrib import admin
from .models import Customer, CustomerNote


class CustomerNoteInline(admin.TabularInline):
    model = CustomerNote
    extra = 0
    fields = ('text', 'is_pinned', 'created_by', 'created_at')
    readonly_fields = ('created_by', 'created_at')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        from accounts.permissions import has_permission
        from .access import is_card_manager
        from django.db.models import Q
        records=super().get_queryset(request)
        if not has_permission(request.user,'customers.candidate_view'):
            return records.filter(is_interviewer=False)
        if not is_card_manager(request.user):
            records=records.exclude(Q(is_interviewer=True)&~Q(assigned_to=request.user)&~Q(created_by=request.user))
        return records

    def get_search_results(self, request, queryset, search_term):
        records,duplicates=super().get_search_results(request,queryset,search_term)
        if request.GET.get('app_label') in ('calls','sales'):
            records=records.filter(is_interviewer=False)
        return records,duplicates

    def get_fieldsets(self, request, obj=None):
        if obj and obj.is_interviewer:
            return [('هویت مصاحبه‌کننده',{'fields':('name','mobile','assigned_to','created_by','created_at','updated_at')})]
        return super().get_fieldsets(request,obj)

    def get_inline_instances(self, request, obj=None):
        return [] if obj and obj.is_interviewer else super().get_inline_instances(request,obj)

    def get_readonly_fields(self, request, obj=None):
        fields=tuple(super().get_readonly_fields(request,obj))
        return fields+('assigned_to','created_by') if obj and obj.is_interviewer else fields

    def has_change_permission(self, request, obj=None):
        if obj and obj.is_interviewer:
            from accounts.permissions import has_permission
            from .access import can_edit_card
            return super().has_change_permission(request,obj) and has_permission(request.user,'customers.candidate_edit') and can_edit_card(request.user,obj)
        return super().has_change_permission(request,obj)

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

    def has_delete_permission(self, request, obj=None):
        from accounts.permissions import has_permission
        return has_permission(request.user, 'customers.delete') and super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(CustomerNote)
class CustomerNoteAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        records=super().get_queryset(request)
        return records if request.user.is_superuser else records.exclude(customer__is_interviewer=True)

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

    def has_delete_permission(self, request, obj=None):
        from accounts.permissions import has_permission
        return has_permission(request.user, 'customers.delete') and super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
