from django import forms
from django.core.exceptions import ValidationError
from django.forms import CheckboxInput

from crm.form_mixins import DuplicateCheckMixin
from .models import Ad, AdPlatform, AdProcess, AdSource


class StyledFormMixin:
    input_classes = (
        'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm '
        'focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, CheckboxInput):
                continue
            existing = widget.attrs.get('class', '')
            widget.attrs['class'] = f'{existing} {self.input_classes}'.strip()


# ─────────────────────────────────────────────
# فرم تبلیغ اصلی
# ─────────────────────────────────────────────
class AdForm(DuplicateCheckMixin, StyledFormMixin, forms.ModelForm):
    duplicate_model = 'ad'
    duplicate_fields = {'ad_number': 'شناسه آگهی'}

    class Meta:
        model = Ad
        fields = [
            'platform', 'process', 'cost', 'source',
            'product', 'ad_number', 'note',
        ]
        widgets = {
            'note': forms.Textarea(attrs={'rows': 3}),
            'cost': forms.NumberInput(attrs={'step': '1000'}),
            'ad_number': forms.TextInput(attrs={
                'placeholder': 'خودکار پر می‌شود',
                'autocomplete': 'off',
                'readonly': 'readonly',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # شناسه آگهی اختیاری — اگه خالی بمونه، خودکار پر می‌شه
        self.fields['ad_number'].required = False

        self.fields['platform'].queryset = AdPlatform.objects.filter(is_active=True)
        from django.db.models import Q
        self.fields['source'].queryset = AdSource.objects.filter(Q(is_active=True) | Q(pk=self.instance.source_id))

        if self.instance.pk and self.instance.platform_id:
            self.fields['process'].queryset = AdProcess.objects.filter(
                platform=self.instance.platform, is_active=True,
            )
        elif 'platform' in self.data:
            try:
                platform_id = int(self.data.get('platform'))
                self.fields['process'].queryset = AdProcess.objects.filter(
                    platform_id=platform_id, is_active=True,
                )
            except (ValueError, TypeError):
                self.fields['process'].queryset = AdProcess.objects.none()
        else:
            self.fields['process'].queryset = AdProcess.objects.none()

        from products.models import Product
        self.fields['product'].queryset = Product.objects.filter(
            stock__gt=0,
        ).order_by('name')
        self.fields['product'].required = False

    def clean_ad_number(self):
        ad_number = (self.cleaned_data.get('ad_number') or '').strip()

        # اگه خالی بود، خودکار از پلتفرم بگیر
        if not ad_number:
            platform = self.cleaned_data.get('platform')
            if platform:
                ad_number = platform.get_next_ad_number()

        if not ad_number:
            raise ValidationError('شناسه آگهی الزامی است.')

        from crm.duplicate_check import find_exact_match, normalize_code
        if find_exact_match(Ad, 'ad_number', ad_number, normalize_code, self.instance.pk):
            raise ValidationError(
                f'شناسه آگهی «{ad_number}» قبلاً ثبت شده است. '
                'شناسه آگهی باید یونیک باشد.'
            )
        return ad_number

    def clean_cost(self):
        cost = self.cleaned_data.get('cost')
        if cost is not None and cost < 0:
            raise ValidationError('هزینه نمی‌تواند منفی باشد.')
        return cost

    def clean(self):
        cleaned = super().clean()
        platform = cleaned.get('platform')
        process = cleaned.get('process')
        if platform and process and process.platform_id != platform.id:
            self.add_error(
                'process',
                'فرآیند انتخاب‌شده به این پلتفرم تعلق ندارد.',
            )
        return cleaned


# ─────────────────────────────────────────────
# فرم‌های مدیریت (فقط ادمین)
# ─────────────────────────────────────────────
class AdPlatformForm(DuplicateCheckMixin, StyledFormMixin, forms.ModelForm):
    duplicate_model = 'adplatform'
    duplicate_fields = {'name': 'نام عنوان'}

    class Meta:
        model = AdPlatform
        fields = ['name', 'ad_number_start', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'مثال: دیوار'}),
            'ad_number_start': forms.NumberInput(attrs={'step': '1'}),
        }

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        from crm.duplicate_check import find_exact_match, normalize_text
        if find_exact_match(AdPlatform, 'name', name, normalize_text, self.instance.pk):
            raise ValidationError('این عنوان قبلاً تعریف شده است.')
        return name


class AdProcessForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = AdProcess
        fields = ['platform', 'name', 'default_cost', 'is_active']
        widgets = {
            'default_cost': forms.NumberInput(attrs={'step': '1'}),
        }

    def clean_platform(self):
        platform = self.cleaned_data['platform']
        if self.instance.pk and platform.pk != self.instance.platform_id and self.instance.ads.exists():
            raise ValidationError('این فرآیند در تبلیغات استفاده شده است؛ عنوان آن قابل جابه‌جایی نیست. برای عنوان دیگر، فرآیند جدید بسازید.')
        return platform

    def clean(self):
        cleaned = super().clean()
        platform, name = cleaned.get('platform'), cleaned.get('name')
        if platform and name:
            from crm.duplicate_check import find_exact_match, normalize_text
            if find_exact_match(AdProcess, 'name', name, normalize_text, self.instance.pk, extra_filter={'platform': platform}):
                self.add_error('name', 'این نام فرآیند برای این عنوان قبلاً تعریف شده است.')
        return cleaned


class AdSourceForm(DuplicateCheckMixin, StyledFormMixin, forms.ModelForm):
    duplicate_model = 'adsource'
    duplicate_fields = {'phone_number': 'شماره تماس'}

    class Meta:
        model = AdSource
        fields = ['phone_number', 'label', 'is_active']

    def clean_phone_number(self):
        from crm.duplicate_check import normalize_phone, find_exact_match
        from crm.numerals import ascii_digits
        raw = ascii_digits(self.cleaned_data['phone_number']).strip()
        if any(character not in '+- ()0123456789۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩' for character in raw):
            raise ValidationError('شماره منبع باید فقط شامل رقم و علائم متداول شماره تلفن باشد.')
        phone = normalize_phone(raw)
        if not phone:
            raise ValidationError('شماره منبع را وارد کنید.')
        if find_exact_match(AdSource, 'phone_number', phone, normalize_phone, self.instance.pk):
            raise ValidationError('این شماره قبلاً ثبت شده است.')
        return phone
