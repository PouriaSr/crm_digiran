from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Ad, AdLog, AdPlatform, AdProcess, AdSource


@admin.register(AdPlatform)
class AdPlatformAdmin(ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(AdProcess)
class AdProcessAdmin(ModelAdmin):
    list_display = ['name', 'platform', 'default_cost', 'is_active']
    list_filter = ['platform', 'is_active']
    search_fields = ['name']


@admin.register(AdSource)
class AdSourceAdmin(ModelAdmin):
    list_display = ['phone_number', 'label', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['phone_number', 'label']


@admin.register(Ad)
class AdAdmin(ModelAdmin):
    list_display = [
        'ad_number', 'platform', 'process', 'cost',
        'source', 'product', 'created_by', 'created_at',
    ]
    list_filter = ['platform', 'process', 'created_by', 'created_at']
    search_fields = ['ad_number', 'source__phone_number', 'product__name']
    readonly_fields = ['created_at', 'created_by']
    date_hierarchy = 'created_at'


@admin.register(AdLog)
class AdLogAdmin(ModelAdmin):
    list_display = ['ad', 'action', 'changed_by', 'changed_at']
    list_filter = ['action', 'changed_at']
    search_fields = ['ad__ad_number', 'changed_by__username']
    readonly_fields = ['ad', 'action', 'changed_by', 'changed_at', 'changes', 'note']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False