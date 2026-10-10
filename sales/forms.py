import jdatetime
from datetime import datetime
from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone
from customers.models import Customer
from products.models import Product
from .models import Invoice, InvoiceItem


class InvoiceForm(forms.ModelForm):
    """فرم سربرگ فاکتور"""

    # ⭐ تاریخ‌ها به‌عنوان CharField برای تقویم شمسی
    issue_date = forms.CharField(
        required=False,
        label='تاریخ صدور',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
            'data-jdp': '',
            'data-jdp-time': 'false',
            'placeholder': '۱۴۰۵/۰۱/۱۵',
            'autocomplete': 'off',
        })
    )
    due_date = forms.CharField(
        required=False,
        label='مهلت پرداخت',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
            'data-jdp': '',
            'data-jdp-time': 'false',
            'placeholder': '۱۴۰۵/۰۱/۱۵',
            'autocomplete': 'off',
        })
    )

    class Meta:
        model = Invoice
        fields = ['customer', 'status', 'payment_type', 'issue_date', 'due_date',
                  'discount', 'tax_percent', 'notes']
        widgets = {
            'customer': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'
            }),
            'payment_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'
            }),
            'discount': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'placeholder': '0', 'min': 0, 'dir': 'ltr'
            }),
            'tax_percent': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'placeholder': '9', 'min': 0, 'max': 100, 'step': '0.01', 'dir': 'ltr'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'rows': 3, 'placeholder': 'توضیحات فاکتور'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk and self.instance.issue_date:
            j = jdatetime.date.fromgregorian(date=self.instance.issue_date)
            self.initial['issue_date'] = j.strftime('%Y/%m/%d')
        else:
            j = jdatetime.date.fromgregorian(date=timezone.now().date())
            self.initial['issue_date'] = j.strftime('%Y/%m/%d')

        if self.instance and self.instance.pk and self.instance.due_date:
            j = jdatetime.date.fromgregorian(date=self.instance.due_date)
            self.initial['due_date'] = j.strftime('%Y/%m/%d')

    def _to_en(self, value):
        persian = '۰۱۲۳۴۵۶۷۸۹'
        arabic = '٠١٢٣٤٥٦٧٨٩'
        for i, (p, a) in enumerate(zip(persian, arabic)):
            value = value.replace(p, str(i)).replace(a, str(i))
        return value

    def clean_issue_date(self):
        value = self.cleaned_data.get('issue_date')
        if not value:
            return timezone.now().date()
        if hasattr(value, 'year'):
            return value

        value = self._to_en(str(value).strip()).replace('-', '/').replace('.', '/')
        if ' ' in value:
            value = value.split(' ', 1)[0]

        try:
            y, m, d = map(int, value.split('/'))
            return jdatetime.date(y, m, d).togregorian()
        except (ValueError, AttributeError):
            raise forms.ValidationError('تاریخ معتبر نیست')

    def clean_due_date(self):
        value = self.cleaned_data.get('due_date')
        if not value:
            return None
        if hasattr(value, 'year'):
            return value

        value = self._to_en(str(value).strip()).replace('-', '/').replace('.', '/')
        if ' ' in value:
            value = value.split(' ', 1)[0]

        try:
            y, m, d = map(int, value.split('/'))
            return jdatetime.date(y, m, d).togregorian()
        except (ValueError, AttributeError):
            raise forms.ValidationError('تاریخ معتبر نیست')


# ═══ فرم قلم فاکتور — پشتیبانی از محصولات soft-deleted ═══
from django.db.models import Q


class InvoiceItemForm(forms.ModelForm):
    """فرم هر قلم فاکتور"""

    class Meta:
        model = InvoiceItem
        fields = ['product', 'quantity', 'unit_price']
        widgets = {
            'product': forms.Select(attrs={
                'class': 'item-product w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'item-qty w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'min': 1, 'placeholder': '1',
            }),
            'unit_price': forms.NumberInput(attrs={
                'class': 'item-price w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'min': 0, 'placeholder': '0', 'dir': 'ltr'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # اگه این قلم قبلاً ذخیره شده و محصولش soft-deleted شده،
        # محصول فعلی رو توی queryset نگه‌دار تا فرم معتبر بمونه
        if self.instance and self.instance.pk and self.instance.product_id:
            current_id = self.instance.product_id
            self.fields['product'].queryset = Product.all_objects.filter(
                Q(is_deleted=False) | Q(pk=current_id)
            )
        else:
            self.fields['product'].queryset = Product.objects.all()


InvoiceItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    extra=3,
    can_delete=True,
)