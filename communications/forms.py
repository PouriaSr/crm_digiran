from django import forms
from django.core.exceptions import ValidationError
from .models import ChannelConfiguration
from .services import PROVIDERS, validate_template


class ConfigurationForm(forms.ModelForm):
    class Meta:
        model = ChannelConfiguration
        fields = ['provider', 'sender', 'credential_env', 'subject', 'message_template']
        widgets = {'message_template': forms.Textarea(attrs={'rows': 5, 'dir': 'auto'})}

    def __init__(self, *args, channel, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel = channel
        self.fields['provider'] = forms.ChoiceField(label='سرویس پیشنهادی', choices=PROVIDERS[channel])
        self.fields['credential_env'] = forms.RegexField(label='نام متغیر اعتبار اتصال', regex=r'^[A-Z][A-Z0-9_]{2,99}$', required=False,
            help_text='فقط نام متغیر محیطی، مثلاً SMS_API_KEY؛ کلید یا رمز واقعی را اینجا وارد نکنید.', error_messages={'invalid': 'نامی مانند SMS_API_KEY با حروف بزرگ انگلیسی وارد کنید.'})
        self.fields['message_template'].validators.append(validate_template)
        self.fields['message_template'].help_text = 'متغیرها با داده نمونه جایگزین می‌شوند. متن به هیچ سرویس بیرونی ارسال نمی‌شود.'
        self.fields['sender'].label = {'sms': 'شماره یا خط فرستنده', 'email': 'ایمیل فرستنده', 'whatsapp': 'شماره فرستنده', 'voip': 'داخلی یا شناسه تماس‌گیرنده'}[channel]
        if channel != 'email':
            self.fields.pop('subject')
        else:
            self.fields['sender'] = forms.EmailField(label='ایمیل فرستنده', required=False)
            self.fields['subject'].validators.append(validate_template)
        if channel in ('sms', 'whatsapp') or (channel == 'email'):
            self.fields['endpoint'] = forms.URLField(label='نشانی API پیشنهادی', required=False, help_text='برای مستندسازی اتصال آینده است؛ فعلاً هیچ درخواست شبکه‌ای به این نشانی اجرا نمی‌شود.')
        if channel in ('email', 'voip'):
            self.fields['host'] = forms.CharField(label='میزبان سرویس', max_length=253, required=False)
            self.fields['port'] = forms.IntegerField(label='پورت', min_value=1, max_value=65535, required=False)
        if channel == 'email':
            self.fields['host'].label = 'میزبان SMTP'
            self.fields['port'].label = 'پورت SMTP'
            self.fields['endpoint'].label = 'نشانی API (برای سرویس API)'
            self.fields['security'] = forms.ChoiceField(label='امنیت اتصال', choices=[('starttls', 'STARTTLS'), ('ssl', 'SSL / TLS')])
            self.fields['username'] = forms.CharField(label='نام کاربری سرویس', max_length=150, required=False)
        if channel == 'whatsapp':
            self.fields['account_id'] = forms.CharField(label='شناسه حساب تجاری / شماره', max_length=150, required=False)
            self.fields['template_id'] = forms.CharField(label='نام قالب تأییدشده', max_length=150, required=False, help_text='برای شروع گفتگو در WhatsApp Business ممکن است قالب تأییدشده لازم باشد؛ اتصال نهایی بعداً انتخاب می‌شود.')
        if channel == 'voip':
            self.fields['transport'] = forms.ChoiceField(label='روش ارتباط پیشنهادی', choices=[('pending', 'بعداً انتخاب می‌شود'), ('ami', 'AMI'), ('ari', 'ARI / HTTP'), ('sip', 'SIP')])
        for name, field in self.fields.items():
            if name not in self._meta.fields:
                field.initial = self.instance.connection.get(name, {'security': 'starttls', 'transport': 'pending'}.get(name, ''))
            field.widget.attrs.setdefault('placeholder', field.label)
        self.fields['credential_env'].widget.attrs['dir'] = 'ltr'

    def save(self, commit=True):
        config = super().save(commit=False)
        config.channel = self.channel
        config.connection = {name: self.cleaned_data[name] for name in self.fields if name not in self._meta.fields}
        if commit:
            config.save()
        return config


class SimulationForm(forms.Form):
    recipient = forms.CharField(label='مقصد تست', max_length=254)
    sample_name = forms.CharField(label='نام مخاطب نمونه', max_length=100, initial='مخاطب آزمایشی')
    company_name = forms.CharField(label='نام مجموعه', max_length=100, initial='دیجیران')
    task_title = forms.CharField(label='عنوان پیگیری نمونه', max_length=150, initial='پیگیری درخواست شما')

    def __init__(self, *args, channel, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel = channel
        if channel == 'email':
            self.fields['recipient'] = forms.EmailField(label='ایمیل مقصد تست', max_length=254, widget=forms.EmailInput(attrs={'placeholder': 'name@example.com', 'dir': 'ltr'}))
        else:
            self.fields['recipient'].label = 'شماره مقصد تست'
            self.fields['recipient'].widget.attrs.update(placeholder='09123456789', dir='ltr', inputmode='tel')
        self.fields['recipient'].help_text = 'این مقصد فقط برای شبیه‌سازی ثبت می‌شود؛ پیام یا تماس واقعی انجام نمی‌شود.'

    def clean_recipient(self):
        value = self.cleaned_data['recipient']
        if self.channel == 'email':
            return value
        import re
        value = value.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789'))
        value = re.sub(r'[\s()-]', '', value)
        if not re.fullmatch(r'(?:0\d{10}|\+\d{8,15}|\d{3,6})', value):
            raise ValidationError('شماره موبایل، شماره بین‌المللی با + یا داخلی ۳ تا ۶ رقمی وارد کنید.')
        if self.channel != 'voip' and re.fullmatch(r'\d{3,6}', value):
            raise ValidationError('برای این کانال، شماره کامل مقصد را وارد کنید.')
        return value


class LogFilterForm(forms.Form):
    q = forms.CharField(label='جستجو در آزمایش‌ها', required=False, max_length=200, widget=forms.TextInput(attrs={'placeholder': 'مقصد، متن یا نام کاربر…'}))
    status = forms.ChoiceField(label='نتیجه', required=False, choices=[('', 'همه نتیجه‌ها'), ('simulated', 'شبیه‌سازی شد'), ('incomplete', 'نیاز به تکمیل')])
    kind = forms.ChoiceField(label='نوع آزمایش', required=False, choices=[('', 'همه آزمایش‌ها'), ('message', 'تست پیام'), ('configuration', 'بررسی تنظیمات')])
    date_from = forms.CharField(label='از تاریخ', required=False, widget=forms.TextInput(attrs={'data-jdp': '', 'placeholder': 'انتخاب تاریخ…'}))
    date_to = forms.CharField(label='تا تاریخ', required=False, widget=forms.TextInput(attrs={'data-jdp': '', 'placeholder': 'انتخاب تاریخ…'}))

    def clean(self):
        data = super().clean()
        from audit.views import _parse_jalali_date
        for key in ('date_from', 'date_to'):
            value = data.get(key)
            parsed = _parse_jalali_date(value)
            if value and not parsed:
                self.add_error(key, 'تاریخ شمسی معتبر وارد کنید.')
            data[key] = parsed
        if data.get('date_from') and data.get('date_to') and data['date_from'] > data['date_to']:
            self.add_error('date_to', 'پایان بازه باید بعد از شروع آن باشد.')
        return data
