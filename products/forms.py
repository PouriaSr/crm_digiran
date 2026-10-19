import re
from django import forms

from crm.duplicate_check import (
    find_similar_matches,
    normalize_code, normalize_text,
)
from crm.form_mixins import DuplicateCheckMixin
from .models import Product, Category


class ProductForm(DuplicateCheckMixin, forms.ModelForm):
    """فرم کالا — با سیستم جامع تشخیص تکراری"""
    duplicate_model = 'product'
    duplicate_fields = {'code': 'کد کالا'}

    class Meta:
        model = Product
        fields = [
            'name', 'code', 'category', 'unit',
            'price', 'cost_price', 'stock', 'min_stock',
            'description', 'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': 'مثلاً iPhone ۱۵ Pro Max'}),
            'code': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': 'مثلاً IPH۱۵PM-۲۵۶', 'dir': 'ltr'}),
            'category': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'unit': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'price': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': '۰', 'dir': 'ltr', 'min': 0}),
            'cost_price': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': '۰', 'dir': 'ltr', 'min': 0}),
            'stock': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': '۰', 'dir': 'ltr', 'min': 0}),
            'min_stock': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': '۰', 'dir': 'ltr', 'min': 0}),
            'description': forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'rows': 3, 'placeholder': 'توضیحات کالا'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.duplicate_warnings = []
        self.fields['category'].queryset = Category.objects.filter(is_active=True)
        self.fields['category'].empty_label = '— انتخاب دسته —'

    def clean_code(self):
        return normalize_code(self.cleaned_data.get('code'))

    def clean(self):
        cleaned = super().clean()
        self.duplicate_warnings = []
        exclude_pk = self.instance.pk if self.instance and self.instance.pk else None

        # ─── Exact block: code ───
        code = cleaned.get('code')
        if code:
            # ⭐ استفاده از all_objects برای چک کردن کالاهای حذف‌شده
            qs = Product.all_objects.filter(code__iexact=code)
            if exclude_pk:
                qs = qs.exclude(pk=exclude_pk)
            
            existing = qs.first()
            if existing:
                if existing.is_deleted:
                    self.add_error('code', f'⛔ کد کالا «{code}» قبلاً برای کالای حذف‌شده «{existing.name}» ثبت شده است. ابتدا آن کالا را از لیست حذف‌شده‌ها بازیابی کنید.')
                else:
                    self.add_error('code', f'⛔ کد کالا «{code}» قبلاً برای «{existing.name}» ثبت شده است.')

        # ─── Similar warn: name ───
        name = cleaned.get('name')
        if name:
            # برای نام، همون کالاهای حذف‌نشده کافیست (چون فقط یک هشدار است)
            for obj, ratio in find_similar_matches(Product, 'name', name, normalize_text, exclude_pk=exclude_pk):
                self.duplicate_warnings.append({
                    'field': 'name', 'label': 'نام کالا',
                    'value': name, 'match': obj, 'ratio': round(ratio * 100, 1),
                })

        return cleaned


class CategoryForm(DuplicateCheckMixin, forms.ModelForm):
    """فرم دسته‌بندی — با سیستم جامع تشخیص تکراری"""
    duplicate_model = 'category'
    duplicate_fields = {
        'name': 'نام دسته',
        'slug': 'نام کوتاه',
    }

    class Meta:
        model = Category
        fields = ['name', 'slug', 'icon', 'description', 'order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': 'مثلاً: موبایل و تبلت'}),
            'slug': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': 'mobile', 'dir': 'ltr'}),
            'icon': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': '📱', 'maxlength': '10'}),
            'description': forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'rows': 3, 'placeholder': 'توضیحات (اختیاری)'}),
            'order': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'min': 0, 'dir': 'ltr'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.duplicate_warnings = []

    def clean_slug(self):
        slug = self.cleaned_data.get('slug', '').strip().lower()
        if not re.match(r'^[a-z0-9\-_]+$', slug):
            raise forms.ValidationError('نام کوتاه باید فقط شامل حروف انگلیسی کوچک، اعداد، - و _ باشد.')
        return slug

    def clean(self):
        cleaned = super().clean()
        self.duplicate_warnings = []
        exclude_pk = self.instance.pk if self.instance and self.instance.pk else None

        # ─── Exact block: name ───
        name = cleaned.get('name')
        if name:
            from crm.duplicate_check import find_exact_match
            existing = find_exact_match(Category, 'name', name, normalize_text, exclude_pk)
            if existing:
                self.add_error('name', f'⛔ دسته‌بندی با همین نام «{existing.name}» قبلاً ثبت شده است.')

        # ─── Similar warn: name ───
        if name:
            for obj, ratio in find_similar_matches(Category, 'name', name, normalize_text,
                                                    threshold=0.90, exclude_pk=exclude_pk):
                self.duplicate_warnings.append({
                    'field': 'name', 'label': 'نام دسته',
                    'value': name, 'match': obj, 'ratio': round(ratio * 100, 1),
                })

        return cleaned