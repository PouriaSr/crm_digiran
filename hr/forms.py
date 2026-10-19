import jdatetime
from django import forms
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from crm.form_mixins import DuplicateCheckMixin
from .models import Employee, Task, LeaveRequest, Attendance


class EmployeeForm(DuplicateCheckMixin, forms.ModelForm):
    duplicate_model = 'employee'
    duplicate_fields = {
        'mobile': 'شماره تماس',
        'national_id': 'کد ملی',
    }

    birth_date = forms.CharField(
        required=False, label='تاریخ تولد',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
            'data-jdp': '', 'data-jdp-time': 'false',
            'placeholder': '۱۳۷۰/۰۱/۱۵', 'autocomplete': 'off',
        })
    )

    class Meta:
        model = Employee
        fields = ['user', 'first_name', 'last_name', 'national_id', 'mobile',
                  'email', 'address', 'birth_date', 'position', 'contract_type',
                  'salary', 'is_active', 'notes']
        widgets = {
            'user': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'first_name': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': 'نام'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': 'نام خانوادگی'}),
            'national_id': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': '۱۲۳۴۵۶۷۸۹۰', 'dir': 'ltr'}),
            'mobile': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': '۰۹۱۲۱۲۳۴۵۶۷', 'dir': 'ltr'}),
            'email': forms.EmailInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'dir': 'ltr'}),
            'address': forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'rows': 2}),
            'position': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'contract_type': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'salary': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': '۰', 'dir': 'ltr', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'}),
            'notes': forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.duplicate_warnings = []

        if self.instance and self.instance.pk:
            self.fields['user'].queryset = User.objects.filter(
                models.Q(employee_profile__isnull=True) |
                models.Q(employee_profile=self.instance)
            )
            if self.instance.birth_date:
                j = jdatetime.date.fromgregorian(date=self.instance.birth_date)
                self.initial['birth_date'] = j.strftime('%Y/%m/%d')
            self.fields['user'].queryset = User.objects.filter(employee_profile__isnull=True)
            
    def _to_en(self, value):
        from crm.duplicate_check import normalize_digits
        return normalize_digits(value)

    def _parse_jalali(self, value):
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

    def clean_birth_date(self):
        return self._parse_jalali(self.cleaned_data.get('birth_date'))

    
    def clean_national_id(self):
        """
        ⭐ Fix #11: چک طول و نوع ارقام، هم‌راستا با CustomerForm.
        Employee.national_id = CharField(max_length=10) است، ولی در MySQL غیر-strict
        مقادیر بلندتر truncate می‌شوند و در PostgreSQL خطای 500 می‌دهند.
        """
        from crm.duplicate_check import normalize_digits
        nid = normalize_digits(
            self.cleaned_data.get('national_id', '')
        ).replace(' ', '').replace('-', '')

        # خالی مجاز است (بعضی کارمندان کد ملی نداده‌اند)
        if not nid:
            return ''

        if not nid.isdigit():
            raise forms.ValidationError('کد ملی باید فقط شامل ارقام باشد.')

        if len(nid) != 10:
            raise forms.ValidationError('کد ملی باید دقیقاً ۱۰ رقم باشد.')

        return nid

    def clean_mobile(self):
        from crm.duplicate_check import normalize_phone
        return normalize_phone(self.cleaned_data.get('mobile'))

    def clean(self):
        from crm.duplicate_check import (
            find_exact_match, find_similar_fullname,
            normalize_digits, normalize_phone, normalize_text,
        )
        cleaned = super().clean()
        self.duplicate_warnings = []
        exclude_pk = self.instance.pk if self.instance and self.instance.pk else None

        nid = cleaned.get('national_id')
        if nid:
            existing = find_exact_match(Employee, 'national_id', nid, normalize_digits, exclude_pk)
            if existing:
                self.add_error('national_id', f'⛔ کد ملی «{nid}» قبلاً برای «{existing.full_name}» ثبت شده است.')

        mobile = cleaned.get('mobile')
        if mobile:
            existing = find_exact_match(Employee, 'mobile', mobile, normalize_phone, exclude_pk)
            if existing:
                self.add_error('mobile', f'⛔ شماره تماس «{mobile}» قبلاً برای «{existing.full_name}» ثبت شده است.')

        first = cleaned.get('first_name') or ''
        last = cleaned.get('last_name') or ''
        combined = f'{first} {last}'.strip()
        if combined:
            for obj, ratio in find_similar_fullname(Employee, combined, normalize_text, exclude_pk=exclude_pk):
                self.duplicate_warnings.append({
                    'field': 'first_name', 'label': 'نام و نام خانوادگی',
                    'value': combined, 'match': obj, 'ratio': round(ratio * 100, 1),
                })

        return cleaned


class TaskForm(forms.ModelForm):
    due_date = forms.CharField(
        required=False, label='مهلت انجام',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
            'data-jdp': '', 'data-jdp-time': 'false',
            'placeholder': '۱۴۰۵/۰۱/۱۵', 'autocomplete': 'off',
        })
    )

    class Meta:
        model = Task
        fields = ['title', 'description', 'assigned_to', 'priority',
                  'status', 'due_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': 'عنوان وظیفه'}),
            'description': forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'rows': 4, 'placeholder': 'توضیحات وظیفه'}),
            'assigned_to': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'priority': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'status': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].queryset = Employee.objects.filter(is_active=True)

        if self.instance and self.instance.pk and self.instance.due_date:
            j = jdatetime.date.fromgregorian(date=self.instance.due_date)
            self.initial['due_date'] = j.strftime('%Y/%m/%d')

    def _to_en(self, value):
        persian = '۰۱۲۳۴۵۶۷۸۹'
        arabic = '٠١٢٣٤٥٦٧٨٩'
        for i, (p, a) in enumerate(zip(persian, arabic)):
            value = value.replace(p, str(i)).replace(a, str(i))
        return value

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


class LeaveRequestForm(forms.ModelForm):
    start_date = forms.CharField(
        label='از تاریخ',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
            'data-jdp': '', 'data-jdp-time': 'false',
            'placeholder': '۱۴۰۵/۰۱/۱۵', 'autocomplete': 'off',
        })
    )
    end_date = forms.CharField(
        label='تا تاریخ',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
            'data-jdp': '', 'data-jdp-time': 'false',
            'placeholder': '۱۴۰۵/۰۱/۱۵', 'autocomplete': 'off',
        })
    )

    class Meta:
        model = LeaveRequest
        fields = ['employee', 'leave_type', 'start_date', 'end_date', 'reason']
        widgets = {
            'employee': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'
            }),
            'leave_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'
            }),
            'reason': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'rows': 3, 'placeholder': 'علت مرخصی'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        from accounts.permissions import has_permission

        employee_qs = Employee.objects.filter(is_active=True)

        if self.user and not has_permission(self.user, 'hr.review_leaves'):
            if hasattr(self.user, 'employee_profile'):
                employee_qs = Employee.objects.filter(pk=self.user.employee_profile.pk)
                self.fields['employee'].initial = self.user.employee_profile
            else:
                employee_qs = Employee.objects.none()

        self.fields['employee'].queryset = employee_qs

        if self.instance and self.instance.pk:
            if self.instance.start_date:
                j = jdatetime.date.fromgregorian(date=self.instance.start_date)
                self.initial['start_date'] = j.strftime('%Y/%m/%d')
            if self.instance.end_date:
                j = jdatetime.date.fromgregorian(date=self.instance.end_date)
                self.initial['end_date'] = j.strftime('%Y/%m/%d')

    def _to_en(self, value):
        persian = '۰۱۲۳۴۵۶۷۸۹'
        arabic = '٠١٢٣٤٥٦٧٨٩'
        for i, (p, a) in enumerate(zip(persian, arabic)):
            value = value.replace(p, str(i)).replace(a, str(i))
        return value

    def _parse_jalali(self, value):
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

    def clean_start_date(self):
        return self._parse_jalali(self.cleaned_data.get('start_date'))

    def clean_end_date(self):
        return self._parse_jalali(self.cleaned_data.get('end_date'))

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        if start and end and end < start:
            raise forms.ValidationError('تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد')
        return cleaned


class AttendanceForm(forms.ModelForm):

    class Meta:
        model = Attendance
        fields = ['employee', 'check_in', 'check_out', 'status', 'notes']
        widgets = {
            'employee': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'
            }),
            'check_in': forms.TimeInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'type': 'time'
            }),
            'check_out': forms.TimeInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'type': 'time'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'rows': 2
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Employee.objects.filter(is_active=True)

        
    def _to_en(self, value):
        persian = '۰۱۲۳۴۵۶۷۸۹'
        arabic = '٠١٢٣٤٥٦٧٨٩'
        for i, (p, a) in enumerate(zip(persian, arabic)):
            value = value.replace(p, str(i)).replace(a, str(i))
        return value

    

# ═══════════════════════════════════════════════════════════
# فرم ویرایش پروفایل شخصی
# ═══════════════════════════════════════════════════════════
class MyProfileForm(forms.ModelForm):
    """فرم ویرایش پروفایل برای خود کاربر"""

    class Meta:
        model = Employee
        fields = ['first_name', 'last_name', 'mobile', 'email', 'address', 'birth_date']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'mobile': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': '۰۹۱۲۱۲۳۴۵۶۷', 'dir': 'ltr'}),
            'email': forms.EmailInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'dir': 'ltr'}),
            'address': forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'rows': 3}),
            'birth_date': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
                'data-jdp': '', 'data-jdp-time': 'false',
                'placeholder': '۱۳۷۰/۰۱/۱۵', 'autocomplete': 'off',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.birth_date:
            j = jdatetime.date.fromgregorian(date=self.instance.birth_date)
            self.initial['birth_date'] = j.strftime('%Y/%m/%d')

    def clean_birth_date(self):
        value = self.cleaned_data.get('birth_date')
        if not value:
            return None
        if hasattr(value, 'year'):
            return value
        from crm.duplicate_check import normalize_digits
        value = normalize_digits(str(value).strip()).replace('-', '/').replace('.', '/')
        if ' ' in value:
            value = value.split(' ', 1)[0]
        try:
            y, m, d = map(int, value.split('/'))
            return jdatetime.date(y, m, d).togregorian()
        except (ValueError, AttributeError):
            raise forms.ValidationError('تاریخ معتبر نیست')