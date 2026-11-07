from django.contrib import admin

from .models import ChannelConfiguration, MessageTemplate, TestRun


@admin.register(ChannelConfiguration)
class ChannelConfigurationAdmin(admin.ModelAdmin):
    list_display = ('channel', 'provider', 'sender', 'updated_by', 'updated_at')
    list_filter = ('channel', 'provider')
    search_fields = ('sender', 'credential_env')


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'channel', 'category', 'is_active', 'is_suggested', 'updated_by', 'updated_at')
    list_filter = ('channel', 'category', 'is_active', 'is_suggested')
    search_fields = ('name', 'subject', 'body')


@admin.register(TestRun)
class TestRunAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'channel', 'kind', 'status', 'recipient', 'template', 'requested_by')
    list_filter = ('channel', 'kind', 'status', 'created_at')
    search_fields = ('recipient', 'subject', 'rendered_text', 'result', 'requested_by__username')
    readonly_fields = ('channel', 'kind', 'status', 'recipient', 'subject', 'rendered_text', 'custom_text',
                       'template', 'result', 'requested_by', 'created_at')
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # مدیر کل صفحه جزئیات فقط‌خواندنی را باز می‌کند تا به دکمه حذف ادمین برسد.
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        # تاریخچه فقط از همین پنل و فقط توسط مدیر کل قابل حذف است.
        return request.user.is_superuser
