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

    def __init__(self, *args, definition=None, scope=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.definition = definition
        if not scope:
            from .structure_registry import component_scopes
            scope=self.instance.scope_key or (next(iter(component_scopes(self.instance.key,definition)),None) if definition else None)
        if definition:
            for key in ('kind','url','scope_path','body'):
                self.fields.pop(key)
        if definition and not definition.get('label_mutable',True):
            self.fields['label'].disabled=True
            self.fields['label'].help_text='این عنوان از اطلاعات رکورد گرفته می‌شود و با تنظیمات نمایش جایگزین نمی‌شود.'
        if definition and definition['kind'] in ('button','link'):
            self.fields['action_kind']=forms.ChoiceField(label='عملکرد دکمه',choices=[('current','عملکرد اصلی'),('navigate','بازکردن مسیر دیگر'),('workflow','گردش‌کار همین رکورد'),('popup','بازکردن پنجره راهنما یا انتخاب')],initial=self.instance.behavior.get('action_kind','current'),required=False)
            self.fields['destination']=forms.CharField(label='مسیر مقصد داخل سیستم',required=False,initial=self.instance.behavior.get('destination',''))
            self.fields['appearance']=forms.ChoiceField(label='ظاهر دکمه',choices=[('default','ظاهر اصلی'),('primary','اصلی'),('secondary','ساده'),('danger','هشدار')],required=False,initial=self.instance.behavior.get('appearance','default'))
            self.fields['confirmation']=forms.CharField(label='پیام تأیید قبل از اقدام',max_length=300,required=False,initial=self.instance.behavior.get('confirmation',''))
            self.fields['popup_text']=forms.CharField(label='متن پنجره',max_length=2000,required=False,widget=forms.Textarea(attrs={'rows':3}),initial=self.instance.behavior.get('popup_text',''))
            targets=[('','فقط نمایش متن')]
            if scope:
                from .models import SectionSchema
                from .behavior_service import prototypes
                section=SectionSchema.objects.filter(key=scope).first()
                if section:
                    from .structure_registry import FORM_TEMPLATES,SECTIONS
                    from django.utils.module_loading import import_string
                    paths=[path for path in FORM_TEMPLATES.get(definition.get('path',''),[]) if path in SECTIONS.get(scope,{}).get('forms',[])]
                    names=set().union(*(set(import_string(path).base_fields) for path in paths)) if paths else set()
                    targets += [(name,str(field.label or name)) for name,field in prototypes(section).items() if (name in names or paths and name.startswith('extra_')) and isinstance(field,(forms.ChoiceField,forms.ModelChoiceField))]
            self.fields['popup_target']=forms.ChoiceField(label='ورودی قابل انتخاب در پنجره',required=False,choices=targets,initial=self.instance.behavior.get('popup_target',''))
            if len(targets)==1:
                self.fields['popup_target'].widget=forms.HiddenInput()
                self.fields['popup_target'].initial=''
            self.fields['tooltip']=forms.CharField(label='راهنمای دکمه',max_length=300,required=False,initial=self.instance.behavior.get('tooltip',''))
        self.fields['label'].required = True
        self.fields['label'].max_length = 180
        for field in self.fields.values():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.HiddenInput)):
                field.widget.attrs.update({'class':'w-full border border-slate-200 rounded-xl p-3 text-sm'})

    def clean(self):
        data = super().clean()
        for key in ('url','scope_path','destination'):
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
        if data.get('action_kind')=='navigate' and not data.get('destination'):self.add_error('destination','مسیر مقصد را وارد کنید.')
        if not self.definition and not data.get('url') and not data.get('body','').strip():
            self.add_error('body', 'متن صفحه یا مسیر مقصد را وارد کنید.')
        if data.get('action_kind')=='popup' and not data.get('popup_text','').strip():self.add_error('popup_text','متن پنجره را وارد کنید.')
        return data

    def save(self,commit=True):
        item=super().save(commit=False)
        if 'action_kind' in self.fields:item.behavior={key:self.cleaned_data.get(key,'') for key in ('action_kind','destination','appearance','confirmation','tooltip','popup_text','popup_target')}
        if commit:item.save()
        return item
