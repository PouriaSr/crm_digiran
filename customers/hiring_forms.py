from datetime import datetime
import hashlib
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import jdatetime
from django import forms
from django.contrib.auth.models import Group
from django.db.models import Q
from django.utils import timezone

from accounts.models import UserRoleProfile
from accounts.permissions import ROLE_DISPLAY, ROLE_TO_GROUP
from crm.duplicate_check import find_exact_match, normalize_digits
from crm.numerals import normalize_input
from .models import Customer, HiringAd, InterviewSession
from .scheduling import parse_followup_time


def role_choices():
    choices = [('role:' + key, title) for key, title in ROLE_DISPLAY.items()]
    known = set(ROLE_TO_GROUP.values()) | set(ROLE_DISPLAY)
    choices += [('group:' + str(group.pk), group.name) for group in Group.objects.exclude(name__in=known).order_by('name')]
    choices += [('title:' + hashlib.sha256(title.encode()).hexdigest()[:24], title) for title in UserRoleProfile.objects.exclude(display_name='').order_by('display_name').values_list('display_name', flat=True).distinct()]
    return choices


def local_parts(value):
    if not value:
        return '', ''
    value = timezone.localtime(value)
    return jdatetime.date.fromgregorian(date=value.date()).strftime('%Y/%m/%d'), value.strftime('%H:%M')


def parse_appointment(form, prefix, required):
    day = form.cleaned_data.get(prefix + '_date', '')
    hour = form.cleaned_data.get(prefix + '_time', '')
    if not required:
        return None
    value = None
    try:
        year, month, date = map(int, normalize_input(day).replace('-', '/').replace('.', '/').split('/'))
        value = jdatetime.date(year, month, date).togregorian()
    except (ValueError, TypeError):
        form.add_error(prefix + '_date', 'تاریخ شمسی معتبر را وارد کنید.')
    time = parse_followup_time(hour)
    if time is None:
        form.add_error(prefix + '_time', 'ساعت معتبر مانند ۱۴:۳۰ وارد کنید.')
    return timezone.make_aware(datetime.combine(value, time)) if value and time else None


def validate_national_id(value, customer):
    value = normalize_digits(value).replace(' ', '').replace('-', '')
    if not value.isascii() or not value.isdigit() or len(value) != 10 or len(set(value)) == 1:
        raise forms.ValidationError('کد ملی باید ۱۰ رقم و معتبر باشد.')
    remainder = sum(int(value[i]) * (10 - i) for i in range(9)) % 11
    if int(value[-1]) != (remainder if remainder < 2 else 11 - remainder):
        raise forms.ValidationError('کد ملی واردشده معتبر نیست.')
    if find_exact_match(Customer, 'national_id', value, normalize_digits, customer.pk, manager=Customer.all_objects):
        raise forms.ValidationError('این کد ملی برای فرد دیگری ثبت شده است.')
    return value


class HiringStyledForm:
    def style(self):
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'w-full border border-gray-200 rounded-xl px-3 py-2.5 bg-white text-sm')


class ResumeForm(HiringStyledForm, forms.Form):
    resume = forms.FileField(label='بارگذاری رزومه', required=False, widget=forms.ClearableFileInput(attrs={'accept': '.pdf,.doc,.docx'}))
    job_ad = forms.ModelChoiceField(label='آگهی موقعیت شغلی', queryset=HiringAd.objects.filter(is_active=True), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['resume'].widget.attrs['id'] = 'arrival-resume'
        self.fields['job_ad'].widget.attrs['id'] = 'arrival-job-ad'
        self.style()

    def clean_resume(self):
        upload = self.cleaned_data.get('resume')
        if not upload:
            return None
        extension = Path(upload.name).suffix.lower()
        if extension not in ('.pdf', '.doc', '.docx') or upload.size > 10 * 1024 * 1024:
            raise forms.ValidationError('رزومه باید PDF، DOC یا DOCX و حداکثر ۱۰ مگابایت باشد.')
        header = upload.read(8)
        upload.seek(0)
        valid = extension == '.pdf' and header.startswith(b'%PDF-') or extension == '.doc' and header == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
        if extension == '.docx':
            try:
                with ZipFile(upload) as document:
                    valid = 'word/document.xml' in document.namelist()
            except (BadZipFile, OSError):
                valid = False
            finally:
                upload.seek(0)
        if not valid:
            raise forms.ValidationError('محتوای فایل با نوع رزومه انتخاب‌شده سازگار نیست.')
        return upload


class HiringAdForm(HiringStyledForm, forms.ModelForm):
    role_key = forms.ChoiceField(label='عنوان / سمت', choices=())

    class Meta:
        model = HiringAd
        fields = ['platform', 'role_key', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role_key'].choices = [('', 'انتخاب سمت…')] + role_choices()
        self.style()


class InterviewForm(HiringStyledForm, forms.ModelForm):
    national_id = forms.CharField(label='کد ملی', max_length=10, required=True, widget=forms.TextInput(attrs={'inputmode': 'numeric', 'dir': 'ltr', 'placeholder': 'لطفاً کد ملی را وارد کنید'}))
    proposed_role = forms.ChoiceField(label='سمت پیشنهادی', choices=(), required=False)
    next_date = forms.CharField(label='تاریخ مصاحبه دوم', required=False, widget=forms.TextInput(attrs={'data-jdp': '', 'autocomplete': 'off'}))
    next_time = forms.CharField(label='ساعت مصاحبه دوم', required=False, widget=forms.TimeInput(attrs={'type': 'time'}))
    invitation_date = forms.CharField(label='تاریخ دعوت', required=False, widget=forms.TextInput(attrs={'data-jdp': '', 'autocomplete': 'off'}))
    invitation_time = forms.CharField(label='ساعت دعوت', required=False, widget=forms.TimeInput(attrs={'type': 'time'}))

    class Meta:
        model = InterviewSession
        fields = ['job_ad', 'national_id', 'behavior', 'fit', 'seriousness', 'questions', 'notes', 'grade', 'result', 'rejection_reason', 'proposed_role', 'experience', 'next_date', 'next_time', 'invite', 'will_attend', 'invitation_date', 'invitation_time', 'collaboration']
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, customer, can_documents=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.customer = customer
        self.fields['job_ad'].label = 'آگهی انتخاب‌شده برای این موقعیت'
        self.fields['job_ad'].queryset = HiringAd.objects.filter(Q(is_active=True) | Q(pk=self.instance.job_ad_id))
        for name in ('job_ad', 'behavior', 'fit', 'seriousness', 'questions', 'grade', 'result'):
            self.fields[name].required = True
        choices = role_choices()
        if self.instance.proposed_role and self.instance.proposed_role not in dict(choices):
            choices.append((self.instance.proposed_role, self.instance.proposed_role_title))
        self.fields['proposed_role'].choices = [('', 'انتخاب سمت…')] + choices
        if can_documents:
            self.initial['national_id'] = customer.national_id
        else:
            self.fields.pop('national_id')
        self.initial['next_date'], self.initial['next_time'] = local_parts(self.instance.next_interview_at)
        self.initial['invitation_date'], self.initial['invitation_time'] = local_parts(self.instance.invitation_at)
        self.style()

    def clean_national_id(self):
        return validate_national_id(self.cleaned_data['national_id'], self.customer)

    def clean(self):
        data = super().clean()
        result = data.get('result')
        if result == 'rejected' and not data.get('rejection_reason'):
            self.add_error('rejection_reason', 'دلیل رد شدن را انتخاب کنید.')
        if result == 'accepted':
            for name in ('proposed_role', 'experience'):
                if not data.get(name):
                    self.add_error(name, 'این فیلد برای نتیجه قبول الزامی است.')
        data['next_interview_at'] = parse_appointment(self, 'next', result == 'repeat')
        if data.get('invite') and result != 'accepted':
            self.add_error('invite', 'دعوت به همکاری فقط برای نتیجه قبول قابل ثبت است.')
        if data.get('invite') and not data.get('will_attend'):
            self.add_error('will_attend', 'وضعیت حضور را انتخاب کنید.')
        data['invitation_at'] = parse_appointment(self, 'invitation', bool(data.get('invite')))
        if result != 'rejected':
            data['rejection_reason'] = ''
        if result != 'accepted':
            data['proposed_role'], data['experience'] = '', ''
        if not data.get('invite'):
            data['will_attend'], data['collaboration'] = '', ''
        return data
