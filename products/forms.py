from django import forms
import re
from .models import Product, Category


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'code', 'category', 'unit',
            'price', 'cost_price',
            'stock', 'min_stock',
            'description', 'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'placeholder': 'مثلاً iPhone 15 Pro Max'
            }),
            'code': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'placeholder': 'مثلاً IPH15PM-256',
                'dir': 'ltr'
            }),
            'category': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'
            }),
            'unit': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'placeholder': '0', 'dir': 'ltr', 'min': 0
            }),
            'cost_price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'placeholder': '0', 'dir': 'ltr', 'min': 0
            }),
            'stock': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'placeholder': '0', 'dir': 'ltr', 'min': 0
            }),
            'min_stock': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'placeholder': '0', 'dir': 'ltr', 'min': 0
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'rows': 3, 'placeholder': 'توضیحات کالا'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(is_active=True)
        self.fields['category'].empty_label = '— انتخاب دسته —'


class CategoryForm(forms.ModelForm):
    """فرم ثبت/ویرایش دسته‌بندی"""

    class Meta:
        model = Category
        fields = ['name', 'slug', 'icon', 'description', 'order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'placeholder': 'مثلاً: موبایل و تبلت'
            }),
            'slug': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'placeholder': 'mobile',
                'dir': 'ltr',
            }),
            'icon': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'placeholder': '📱',
                'maxlength': '10',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'rows': 3,
                'placeholder': 'توضیحات (اختیاری)'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'min': 0, 'dir': 'ltr'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
            }),
        }

    def clean_slug(self):
        slug = self.cleaned_data.get('slug', '').strip().lower()
        if not re.match(r'^[a-z0-9\-_]+$', slug):
            raise forms.ValidationError(
                'نام کوتاه باید فقط شامل حروف انگلیسی کوچک، اعداد، - و _ باشد.'
            )
        return slug