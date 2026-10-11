from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'verbose_name', 'object_repr', 'action', 'user')
    list_filter = ('action', 'model_name', 'created_at')
    search_fields = ('object_repr', 'description')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    readonly_fields = (
        'content_type', 'object_id', 'object_repr', 'model_name',
        'verbose_name', 'action', 'user', 'changes', 'description',
        'ip_address', 'user_agent', 'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
