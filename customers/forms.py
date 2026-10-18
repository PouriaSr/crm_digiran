import jdatetime
from django import forms

from crm.duplicate_check import (
    find_exact_match, find_similar_matches,
    normalize_digits, normalize_email, normalize_phone, normalize_text,
)
from .models import Customer, CustomerNote


class CustomerForm(forms.ModelForm):
    """فرم مشتری — با سیستم جامع تشخیص تکراری"""

    birth_date = forms.CharField(
        required=False, label='تاریخ تولد',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
            'data-jdp': '', 'placeholder': '۱۴۰۵/۰۱/۱۵', 'autocomplete': 'off',
        })
    )

    class Meta:
        model = Customer
        fields = [
            'name', 'mobile', 'email', 'national_id', 'birth_date',
            'status', 'source', 'assigned_to', 'address', 'notes',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': 'نام و نام خانوادگی یا نام شرکت'}),
            'mobile': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': '۰۹۱۲۱۲۳۴۵۶۷', 'dir': 'ltr'}),
            'email': forms.EmailInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': 'email@example.com', 'dir': 'ltr'}),
            'national_id': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': '۱۲۳۴۵۶۷۸۹۰', 'dir': 'ltr'}),
            'status': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'source': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'assigned_to': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'address': forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'rows': 3, 'placeholder': 'آدرس کامل'}),
            'notes': forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'rows': 3, 'placeholder': 'یادداشت‌ها'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.duplicate_warnings = []
        if self.instance and self.instance.pk and self.instance.birth_date:
            g = self.instance.birth_date
            j = jdatetime.date.fromgregorian(date=g)
            self.initial['birth_date'] = j.strftime('%Y/%m/%d')

    # ═══════════════════════════════════════════════════════════
    # نرمال‌سازی ورودی‌ها
    # ═══════════════════════════════════════════════════════════
    def clean_mobile(self):
        return normalize_phone(self.cleaned_data.get('mobile'))

    def clean_national_id(self):
        return normalize_digits(self.cleaned_data.get('national_id', '')).replace(' ', '').replace('-', '')

    def clean_email(self):
        email = self.cleaned_data.get('email', '')
        return str(email).strip().lower() if email else ''

    def clean_birth_date(self):
        value = self.cleaned_data.get('birth_date')
        if not value:
            return None
        if hasattr(value, 'year'):
            return value
        value = normalize_digits(str(value).strip()).replace('-', '/').replace('.', '/')
        if ' ' in value:
            value = value.split(' ', 1)[0]
        parts = value.split('/')
        if len(parts) != 3:
            raise forms.ValidationError('فرمت تاریخ باید به‌صورت ۱۳۷۸/۱۲/۱۶ باشد')
        try:
            y, m, d = map(int, parts)
            return jdatetime.date(y, m, d).togregorian()
        except (ValueError, TypeError):
            raise forms.ValidationError('تاریخ وارد شده معتبر نیست')

    # ═══════════════════════════════════════════════════════════
    # چک تکراری
    # ═══════════════════════════════════════════════════════════
    def clean(self):
        cleaned = super().clean()
        self.duplicate_warnings = []

        exclude_pk = self.instance.pk if self.instance and self.instance.pk else None

        # ─── Exact blocks ───
        mobile = cleaned.get('mobile')
        if mobile:
            existing = find_exact_match(Customer, 'mobile', mobile, normalize_phone, exclude_pk)
            if existing:
                self.add_error('mobile', f'⛔ شماره تماس «{mobile}» قبلاً برای «{existing.name}» ثبت شده است.')

        nid = cleaned.get('national_id')
        if nid:
            existing = find_exact_match(Customer, 'national_id', nid, normalize_digits, exclude_pk)
            if existing:
                self.add_error('national_id', f'⛔ کد ملی «{nid}» قبلاً برای «{existing.name}» ثبت شده است.')

        # ─── Similar warnings ───
        name = cleaned.get('name')
        if name:
            for obj, ratio in find_similar_matches(Customer, 'name', name, normalize_text, exclude_pk=exclude_pk):
                self.duplicate_warnings.append({
                    'field': 'name', 'label': 'نام مشتری',
                    'value': name, 'match': obj, 'ratio': round(ratio * 100, 1),
                })

        email = cleaned.get('email')
        if email:
            for obj, ratio in find_similar_matches(Customer, 'email', email, normalize_email, exclude_pk=exclude_pk):
                self.duplicate_warnings.append({
                    'field': 'email', 'label': 'ایمیل',
                    'value': email, 'match': obj, 'ratio': round(ratio * 100, 1),
                })

        return cleaned


class CustomerNoteForm(forms.ModelForm):
    """فرم ثبت/ویرایش یادداشت مشتری"""

    class Meta:
        model = CustomerNote
        fields = ['text', 'is_pinned']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'rows': 3, 'placeholder': 'متن یادداشت...'}),
            'is_pinned': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'}),
        }

    def clean_text(self):
        text = self.cleaned_data.get('text', '').strip()
        if not text:
            raise forms.ValidationError('متن یادداشت نمی‌تواند خالی باشد.')
        return text