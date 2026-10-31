import jdatetime
from datetime import datetime
from django import forms
from django.utils import timezone
from .models import Call


class CallForm(forms.ModelForm):
    follow_up_time = forms.CharField(label='ساعت پیگیری', required=False,
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'w-full px-4 py-2.5 border rounded-lg', 'dir': 'ltr'}))

    def clean_follow_up_time(self):
        from customers.scheduling import parse_followup_time
        value = self.cleaned_data.get('follow_up_time')
        if not value:
            return None
        parsed = parse_followup_time(value)
        if parsed is None:
            raise forms.ValidationError('ساعت پیگیری معتبر نیست.')
        return parsed

    # ⭐ تعریف صریح به‌عنوان CharField تا Django اون‌ها رو تاریخ میلادی نگیره
    follow_up_date = forms.CharField(
        required=False,
        label='تاریخ پیگیری',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
            'data-jdp': '',
            'data-jdp-time': 'false',
            'placeholder': '۱۴۰۵/۰۱/۱۵',
            'autocomplete': 'off',
        })
    )

    class Meta:
        model = Call
        fields = [
            'customer', 'caller_name', 'call_number', 'source',
            'call_type', 'status', 'purpose',
            'duration',
            'follow_up_date', 'follow_up_time', 'is_followed_up',
            'notes', 'called_by',
        ]
        widgets = {
            'customer': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'
            }),
            'caller_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'placeholder': 'نام شخص تماس‌گیرنده'
            }),
            'call_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'placeholder': '۰۹۱۲۱۲۳۴۵۶۷', 'dir': 'ltr'
            }),
            'call_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'id': 'id_status_field',
            }),
            'purpose': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'
            }),
            'duration': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'placeholder': 'مثلاً ۵', 'min': 0
            }),
            'is_followed_up': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500',
                'id': 'id_followup_checkbox',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'rows': 4, 'placeholder': 'خلاصه مکالمه و نکات مهم...'
            }),
            'called_by': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)# ═══ مقدار اولیه برای تاریخ پیگیری ═══
        from ads.models import AdSource
        from django.db.models import Q
        self.fields['source'].queryset = AdSource.objects.filter(Q(is_active=True) | Q(pk=self.instance.source_id))
        self.fields['source'].required = not self.instance.pk or bool(self.instance.source_id)
        self.fields['source'].widget.attrs['class'] = 'w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm'
        # Older edit clients omit this field; preserve that call's own source.
        if self.is_bound and self.instance.pk and 'source' not in self.data:
            self.data = self.data.copy()
            self.data['source'] = self.instance.source_id or ''
        if self.instance and self.instance.pk and self.instance.follow_up_date:
            g = self.instance.follow_up_date
            j = jdatetime.date.fromgregorian(date=g)
            self.initial['follow_up_date'] = j.strftime('%Y/%m/%d')

    # ═══ متد کمکی ═══
    def _to_en_digits(self, value):
        from crm.numerals import normalize_input
        return normalize_input(value)

    # ═══ اعتبارسنجی تاریخ و ساعت تماس ═══
    
    # ═══ اعتبارسنجی تاریخ پیگیری ═══
    def clean_follow_up_date(self):
        value = self.cleaned_data.get('follow_up_date')
        if not value:
            return None

        if hasattr(value, 'year'):
            return value

        value = self._to_en_digits(str(value).strip())
        value = value.replace('-', '/').replace('.', '/')

        # اگه ساعت هم داشت، جدا کن
        if ' ' in value:
            value = value.split(' ', 1)[0]

        parts = value.split('/')
        if len(parts) != 3:
            raise forms.ValidationError('فرمت تاریخ باید ۱۴۰۵/۰۱/۱۵ باشد')

        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            return jdatetime.date(y, m, d).togregorian()
        except (ValueError, TypeError):
            raise forms.ValidationError('تاریخ معتبر نیست')

    # ═══ اعتبارسنجی سراسری فرم ═══
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        if status == 'followup' or cleaned_data.get('follow_up_date'):
            if not cleaned_data.get('follow_up_date'):
                self.add_error('follow_up_date', 'تاریخ پیگیری الزامی است.')
            if not cleaned_data.get('follow_up_time'):
                self.add_error('follow_up_time', 'ساعت پیگیری الزامی است.')
        is_followed_up = cleaned_data.get('is_followed_up')

        # اگه وضعیت «نیاز به پیگیری» ولی تیک «انجام شده» خورده، تناقض رو حل کن
        if status == 'followup' and is_followed_up:
            cleaned_data['is_followed_up'] = False

        return cleaned_data
