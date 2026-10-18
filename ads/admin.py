from django.contrib import admin
from unfold.admin import ModelAdmin

from .forms import AdForm
from .models import Ad, AdLog, AdPlatform, AdProcess, AdSource


class AdAdminForm(AdForm):
    """
    فرم admin برای Ad — با دو تفاوت مهم نسبت به AdForm سایت:

    1. queryset فرآیندها را روی همه‌ی processهای فعال ست می‌کند
       (سایت از JS برای dynamically filter کردن استفاده می‌کند،
        ولی admin JS ما را ندارد).

    2. rest از منطق AdForm (clean، unique check، platform/process matching)
       دقیقاً همان است — یعنی ادمین هم نمی‌تواند داده‌ی ناسازگار بسازد.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # در admin همه‌ی processهای فعال را نمایش بده
        # (چون JS نداریم که به platform-change واکنش دهد).
        # clean() همچنان تناسب platform.process را enforce می‌کند.
        self.fields['process'].queryset = AdProcess.objects.filter(is_active=True)


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
    # ⭐ Fix #6: استفاده از AdForm به‌جای ModelForm پیش‌فرض
    # این کار همه‌ی اعتبارسنجی‌های clean() را در admin هم فعال می‌کند
    # (مثلاً process متعلق به platform دیگر نمی‌تواند ثبت شود).
    form = AdAdminForm

    list_display = [
        'ad_number', 'platform', 'process', 'cost',
        'source', 'product', 'created_by', 'created_at',
    ]
    list_filter = ['platform', 'process', 'created_by', 'created_at']
    search_fields = ['ad_number', 'source__phone_number', 'product__name']
    readonly_fields = ['created_at', 'created_by']
    date_hierarchy = 'created_at'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


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