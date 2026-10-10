import jdatetime
from django import forms
from .models import Customer


class CustomerForm(forms.ModelForm):
    # ⭐ فیلد تاریخ تولد (بدون ساعت)
    birth_date = forms.CharField(
        required=False,
        label='تاریخ تولد',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
            'data-jdp': '',
            'placeholder': '۱۴۰۵/۰۱/۱۵',
            'autocomplete': 'off',
        })
    )

    class Meta:
        model = Customer
        fields = [
            'name', 'mobile', 'email', 'national_id', 'birth_date',
            'status', 'source', 'assigned_to',
            'address', 'notes',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'placeholder': 'نام و نام خانوادگی یا نام شرکت'
            }),
            'mobile': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'placeholder': '09121234567', 'dir': 'ltr'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'placeholder': 'email@example.com', 'dir': 'ltr'
            }),
            'national_id': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'placeholder': '1234567890', 'dir': 'ltr'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'
            }),
            'source': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'
            }),
            'assigned_to': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'
            }),
            'address': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'rows': 3, 'placeholder': 'آدرس کامل'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'rows': 3, 'placeholder': 'یادداشت‌ها'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # در حالت ویرایش، تاریخ میلادی رو به شمسی تبدیل کن برای نمایش
        if self.instance and self.instance.pk and self.instance.birth_date:
            g = self.instance.birth_date
            j = jdatetime.date.fromgregorian(date=g)
            self.initial['birth_date'] = j.strftime('%Y/%m/%d')

    def clean_birth_date(self):
        value = self.cleaned_data.get('birth_date')
        if not value:
            return None

        # اگه date بود مستقیم برگردون
        if hasattr(value, 'year'):
            return value

        value = str(value).strip()

        # ⭐ تبدیل اعداد فارسی/عربی به انگلیسی
        persian_digits = '۰۱۲۳۴۵۶۷۸۹'
        arabic_digits = '٠١٢٣٤٥٦٧٨٩'
        for i, (p, a) in enumerate(zip(persian_digits, arabic_digits)):
            value = value.replace(p, str(i)).replace(a, str(i))

        # ⭐ یکسان‌سازی جداکننده‌ها
        value = value.replace('-', '/').replace('.', '/')

        # ⭐⭐ این خط کلیدی: اگه ساعت هم داشت، جدا کن و دور بریز
        if ' ' in value:
            value = value.split(' ', 1)[0]

        # تجزیه: سال/ماه/روز
        parts = value.split('/')
        if len(parts) != 3:
            raise forms.ValidationError('فرمت تاریخ باید به‌صورت ۱۳۷۸/۱۲/۱۶ باشد')

        try:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            return jdatetime.date(year, month, day).togregorian()
        except (ValueError, TypeError):
            raise forms.ValidationError('تاریخ وارد شده معتبر نیست')