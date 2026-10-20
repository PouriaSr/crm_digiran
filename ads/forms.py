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
        self.fields['source'].queryset = AdSource.objects.filter(is_active=True)

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

        qs = Ad.objects.filter(ad_number=ad_number)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
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
            'ad_number_start': forms.NumberInput(attrs={'step': '1000'}),
        }

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if AdPlatform.objects.filter(name=name).exclude(pk=self.instance.pk).exists():
            raise ValidationError('این عنوان قبلاً تعریف شده است.')
        return name


class AdProcessForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = AdProcess
        fields = ['platform', 'name', 'default_cost', 'is_active']
        widgets = {
            'default_cost': forms.NumberInput(attrs={'step': '1000'}),
        }


class AdSourceForm(DuplicateCheckMixin, StyledFormMixin, forms.ModelForm):
    duplicate_model = 'adsource'
    duplicate_fields = {'phone_number': 'شماره تماس'}

    class Meta:
        model = AdSource
        fields = ['phone_number', 'label', 'is_active']

    def clean_phone_number(self):
        phone = self.cleaned_data['phone_number'].strip()
        if AdSource.objects.filter(phone_number=phone).exclude(
            pk=self.instance.pk
        ).exists():
            raise ValidationError('این شماره قبلاً ثبت شده است.')
        return phone