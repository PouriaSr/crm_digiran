from urllib.parse import urlsplit
from django import forms
from .models import InterfaceComponent
from .permissions import ROLE_DISPLAY, PERMISSION_META


class InterfaceForm(forms.ModelForm):
    roles = forms.MultipleChoiceField(label='نمایش برای نقش‌ها', choices=list(ROLE_DISPLAY.items()), required=False,
                                     help_text='بدون انتخاب یعنی همه نقش‌ها؛ مجوز اصلی عملیات همچنان لازم است.')
    permission = forms.ChoiceField(label='مجوز لازم برای نمایش', required=False,
                                  choices=[('', 'مجوز فعلی خود بخش')] + [(key, meta[1]) for key, meta in PERMISSION_META.items()])
    revision = forms.IntegerField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = InterfaceComponent
        fields = ['kind', 'label', 'enabled', 'position', 'roles', 'permission', 'url', 'scope_path', 'body', 'revision']
        labels = {'kind':'نوع جزء', 'body':'متن صفحه دلخواه', 'scope_path':'فقط در این مسیر نمایش داده شود'}
        widgets = {'kind': forms.Select(choices=[('tab','تب دلخواه'),('button','دکمه دلخواه')]),
                   'body': forms.Textarea(attrs={'rows':8})}
        help_texts = {'url':'مسیر داخل همین سیستم، مانند /customers/hub/?tab=reception؛ خالی باشد صفحهٔ متنی باز می‌شود.',
                      'scope_path':'خالی یعنی در همه صفحات؛ مانند /customers/hub/', 'body':'متن ساده؛ کد HTML یا JavaScript اجرا نمی‌شود.'}

    def __init__(self, *args, definition=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.definition = definition
        if definition:
            for key in ('kind','url','scope_path','body'):
                self.fields.pop(key)
        if definition and not definition.get('label_mutable',True):
            self.fields['label'].disabled=True
            self.fields['label'].help_text='این عنوان از اطلاعات رکورد گرفته می‌شود و با تنظیمات نمایش جایگزین نمی‌شود.'
        self.fields['label'].required = True
        self.fields['label'].max_length = 180
        for field in self.fields.values():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.HiddenInput)):
                field.widget.attrs.update({'class':'w-full border border-slate-200 rounded-xl p-3 text-sm'})

    def clean(self):
        data = super().clean()
        for key in ('url','scope_path'):
            value = data.get(key, '').strip()
            if value:
                parsed = urlsplit(value)
                if not value.startswith('/') or value.startswith('//') or parsed.scheme or parsed.netloc or '\\' in value or any(ord(c)<32 for c in value):
                    self.add_error(key, 'فقط مسیر داخلی معتبر با یک / در ابتدا مجاز است.')
                if key=='scope_path':
                    from django.urls import get_script_prefix
                    prefix=get_script_prefix().rstrip('/')
                    if prefix and value.startswith(prefix+'/'):data[key]=value[len(prefix):]
                if key=='scope_path' and (parsed.query or parsed.fragment):
                    self.add_error(key, 'مسیر صفحه را بدون پارامتر یا # وارد کنید.')
        if not self.definition and not data.get('url') and not data.get('body','').strip():
            self.add_error('body', 'متن صفحه یا مسیر مقصد را وارد کنید.')
        return data
