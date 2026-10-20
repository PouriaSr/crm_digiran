import jdatetime
from django import forms

from crm.duplicate_check import (
    find_exact_match, find_similar_matches,
    normalize_digits, normalize_email, normalize_phone, normalize_text,
)
from crm.form_mixins import DuplicateCheckMixin
from .models import Customer, CustomerNote


class CustomerForm(DuplicateCheckMixin, forms.ModelForm):
    """فرم مشتری — با سیستم جامع تشخیص تکراری"""
    duplicate_model = 'customer'
    duplicate_fields = {
        'mobile': 'شماره تماس',
        'national_id': 'کد ملی',
    }

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
            'status', 'source', 'ad_source', 'assigned_to', 'address', 'notes',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': 'نام و نام خانوادگی یا نام شرکت'}),
            'mobile': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': '۰۹۱۲۱۲۳۴۵۶۷', 'dir': 'ltr'}),
            'email': forms.EmailInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': 'email@example.com', 'dir': 'ltr'}),
            'national_id': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': '۱۲۳۴۵۶۷۸۹۰', 'dir': 'ltr'}),
            'status': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'ad_source': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'source': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'assigned_to': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'address': forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'rows': 3, 'placeholder': 'آدرس کامل'}),
            'notes': forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'rows': 3, 'placeholder': 'یادداشت‌ها'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.duplicate_warnings = []
        self.fields['status'].choices = [
            ('lead', 'بالقوه (لید)'),
            ('active', 'بالفعل (مشتری)'),
        ]
        from ads.models import AdSource
        self.fields['ad_source'].queryset = AdSource.objects.filter(is_active=True)
        self.fields['ad_source'].required = False
        self.fields['notes'].required = True
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

        # ─── Exact blocks (چک روی فعال + غیرفعال) ───
        mobile = cleaned.get('mobile')
        if mobile:
            existing = find_exact_match(
                Customer, 'mobile', mobile, normalize_phone, exclude_pk,
                manager=Customer.all_objects,
            )
            if existing:
                if existing.is_deleted:
                    self.add_error(
                        'mobile',
                        f'⛔ شماره تماس «{mobile}» قبلاً برای «{existing.name}» ثبت شده '
                        f'ولی آن مشتری غیرفعال شده — ابتدا از صفحه‌ی «مشتریان غیرفعال» بازگردانی کنید.'
                    )
                else:
                    self.add_error(
                        'mobile',
                        f'⛔ شماره تماس «{mobile}» قبلاً برای «{existing.name}» ثبت شده است.'
                    )

        nid = cleaned.get('national_id')
        if nid:
            existing = find_exact_match(
                Customer, 'national_id', nid, normalize_digits, exclude_pk,
                manager=Customer.all_objects,
            )
            if existing:
                tag = ' (غیرفعال)' if existing.is_deleted else ''
                self.add_error(
                    'national_id',
                    f'⛔ کد ملی «{nid}» قبلاً برای «{existing.name}»{tag} ثبت شده است.'
                )

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

class HubCallForm(forms.Form):
    mobile = forms.CharField(label='شماره تماس', max_length=15, required=True,
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg', 'dir': 'ltr', 'placeholder': '09123456789', 'id': 'hub_call_mobile'}))
    name = forms.CharField(label='نام و نام خانوادگی', max_length=200, required=False,
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg', 'id': 'hub_call_name'}))
    call_type = forms.ChoiceField(label='نوع تماس', choices=[
        ('incoming_customer', 'تماس مشتری (ورودی)'),
        ('incoming_missed', 'از دست رفته (ورودی)'),
        ('incoming_chat', 'چت دیوار (ورودی)'),
        ('outgoing', 'تماس خروجی'),
    ], widget=forms.Select(attrs={'class': 'w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all'}))
    source = forms.ModelChoiceField(label='منبع', queryset=__import__('ads.models', fromlist=['AdSource']).AdSource.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg'}))
    customer_type = forms.ChoiceField(label='نوع مشتری', choices=__import__('customers.models', fromlist=['Customer']).Customer.CUSTOMER_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg', 'id': 'hub_customer_type'}))
    installments_count = forms.IntegerField(label='تعداد اقساط', required=False, min_value=1,
        widget=forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg', 'id': 'hub_installments'}))
    cheques_count = forms.IntegerField(label='تعداد چک', required=False, min_value=1, max_value=5,
        widget=forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg', 'id': 'hub_cheques'}))
    notes = forms.CharField(label='توضیحات (الزامی)', required=True,
        widget=forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg', 'rows': 3, 'placeholder': 'شرح مکالمه...'}))
    status = forms.ChoiceField(label='وضعیت مشتری', choices=[('lead', 'بالقوه (نیازمند پیگیری)'), ('active', 'بالفعل (سرنخ)')],
        widget=forms.Select(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg', 'id': 'hub_status'}))
    follow_up_date = forms.CharField(label='تاریخ پیگیری', required=False,
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg', 'data-jdp': '', 'id': 'hub_followup', 'placeholder': '1405/01/01'}))

class HubVisitForm(forms.ModelForm):
    class Meta:
        model = __import__('customers.models', fromlist=['Visit']).Visit
        fields = ['customer', 'is_successful', 'notes']

    customer = forms.ModelChoiceField(label='مشتری', queryset=__import__('customers.models', fromlist=['Customer']).Customer.objects.all(),
        widget=forms.Select(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg'}))
    is_successful = forms.BooleanField(label='مراحل با موفقیت طی شد؟ (انتقال به پرونده)', required=False,
        widget=forms.CheckboxInput(attrs={'class': 'w-5 h-5 text-blue-600 rounded'}))
    notes = forms.CharField(label='یادداشت مراجعه', required=True,
        widget=forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg', 'rows': 3}))
