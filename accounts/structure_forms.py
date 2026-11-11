import re
from copy import deepcopy
from django import forms
from django.core.exceptions import ValidationError
from django.apps import apps
from django.utils.module_loading import import_string
from .models import SectionSchema,SectionField,SectionColumn,SectionStage,SectionTransition
from .structure_registry import SECTIONS
from .permissions import ROLE_DISPLAY,PERMISSION_META
from .structure_service import typed_field,serialized,choice_pairs


class Styled:
    def style(self):
        for field in self.fields.values():
            if not isinstance(field.widget,(forms.CheckboxInput,forms.HiddenInput)):
                field.widget.attrs['class']='w-full border border-slate-200 rounded-xl p-3 text-sm'


def source_choices(section):
    fields=[('extra:'+item.key,item.label+' (سفارشی)') for item in section.fields.filter(enabled=True,native_name='')]
    definition=SECTIONS.get(section.key,{})
    for path in definition.get('fields',[]):
        model=apps.get_model(definition['model'])
        try:
            for part in path.split('__'):
                native=model._meta.get_field(part)
                if native.is_relation:model=native.related_model
            fields.append(('native:'+path,str(native.verbose_name)))
        except Exception:continue
    return [('system:record','جزئیات و گردش‌کار')]+fields


class SectionForm(Styled,forms.ModelForm):
    roles=forms.MultipleChoiceField(label='نقش‌های مجاز',choices=list(ROLE_DISPLAY.items()),required=False)
    permission=forms.ChoiceField(label='مجوز دسترسی',choices=[('','مجوز بخش اصلی')]+[(key,item[1]) for key,item in PERMISSION_META.items()],required=False)
    revision=forms.IntegerField(widget=forms.HiddenInput,required=False)
    class Meta:
        model=SectionSchema
        fields=['label','enabled','roles','permission','position','page_size','sort_source','descending','gate_save','replace_form_logic','revision']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.instance.key!='info':self.fields.pop('replace_form_logic',None)
        if self.instance.custom or not SECTIONS.get(self.instance.key,{}).get('forms'):self.fields.pop('gate_save',None)
        self.fields['page_size'].min_value=5;self.fields['page_size'].max_value=100
        self.fields['sort_source']=forms.ChoiceField(label='مرتب‌سازی پیش‌فرض',required=False,choices=[('','ترتیب فعلی')]+([item for item in source_choices(self.instance) if item[0]!='system:record'] if self.instance.pk else []))
        self.style()
    def clean_page_size(self):
        value=self.cleaned_data['page_size']
        if not 5<=value<=100:raise forms.ValidationError('بین ۵ تا ۱۰۰ وارد کنید.')
        return value
    def clean(self):
        data=super().clean()
        if data.get('gate_save') and (not self.instance.pk or not self.instance.stages.filter(initial=True,enabled=True).exists()):self.add_error('gate_save','ابتدا یک مرحله شروع فعال تعریف کنید.')
        return data


class FieldForm(Styled,forms.ModelForm):
    options=forms.CharField(label='گزینه‌ها، هر گزینه در یک سطر (مقدار | عنوان)',required=False,widget=forms.Textarea(attrs={'rows':4}))
    roles=forms.MultipleChoiceField(label='نقش‌هایی که فیلد را می‌بینند',required=False,choices=list(ROLE_DISPLAY.items()))
    revision=forms.IntegerField(widget=forms.HiddenInput,required=False)
    class Meta:
        model=SectionField
        fields=['label','field_type','native_name','required','enabled','readonly','position','placeholder','help_text','default_value','minimum','maximum','max_length','roles','revision']
    def __init__(self,*args,section,**kwargs):
        self.section=section
        super().__init__(*args,**kwargs)
        self.instance.section=section
        candidates={}
        for path in SECTIONS.get(section.key,{}).get('forms',[]):
            for name,field in import_string(path).base_fields.items():
                if name not in ('id','password','password1','password2'):candidates[name]=str(field.label or name)
        self.fields['native_name']=forms.ChoiceField(label='اتصال به فیلد موجود',required=False,choices=[('','فیلد سفارشی جدید')]+list(candidates.items()),help_text='فیلد جدید داده مستقل دارد؛ اتصال موجود قواعد همان ورودی را تنظیم می‌کند.')
        if self.instance.pk:self.fields['native_name'].disabled=True
        elif self.initial.get('native_name'):
            name=self.initial['native_name']
            for path in SECTIONS.get(section.key,{}).get('forms',[]):
                cls=import_string(path)
                if name not in cls.base_fields:continue
                try:prototype=cls().fields[name]
                except Exception:prototype=cls.base_fields[name]
                self.initial.setdefault('label',str(prototype.label or name));self.initial.setdefault('required',prototype.required)
                inferred='choice' if isinstance(prototype,forms.ChoiceField) else 'decimal' if isinstance(prototype,forms.DecimalField) else 'integer' if isinstance(prototype,forms.IntegerField) else 'boolean' if isinstance(prototype,forms.BooleanField) else 'date' if isinstance(prototype,forms.DateField) else 'longtext' if isinstance(prototype.widget,forms.Textarea) else 'text'
                self.initial.setdefault('field_type',inferred)
                break
        self.initial['options']='\n'.join(value+' | '+label if value!=label else value for value,label in choice_pairs(self.instance))
        self.style()
    def clean(self):
        data=super().clean()
        choices=[]
        for line in data.get('options','').splitlines():
            if not line.strip():continue
            parts=line.split('|',1);value=parts[0].strip();label=parts[-1].strip()
            choices.append({'value':value,'label':label})
        if len(choices)!=len({item['value'] for item in choices}) or len(choices)>100:self.add_error('options','گزینه‌ها باید یکتا و حداکثر ۱۰۰ مورد باشند.')
        if data.get('field_type')=='choice' and not choices and not data.get('native_name'):self.add_error('options','حداقل یک گزینه وارد کنید.')
        if data.get('readonly') and data.get('required') and not data.get('default_value') and not data.get('native_name'):
            self.add_error('default_value','برای فیلد اجباری فقط‌خواندنی، مقدار پیش‌فرض لازم است.')
        native_name=data.get('native_name')
        if native_name:
            for path in SECTIONS.get(self.section.key,{}).get('forms',[]):
                cls=import_string(path)
                if native_name not in cls.base_fields:continue
                model=getattr(getattr(cls,'_meta',None),'model',None)
                try:bound=model._meta.get_field(native_name) if model else None
                except Exception:bound=None
                if bound and not bound.null and not bound.blank and not bound.has_default() and not data.get('required') and not data.get('default_value'):
                    self.add_error('required','این ورودی در ساختار اصلی داده الزامی است؛ مقدار پیش‌فرض معتبر تعیین کنید یا الزامی بماند.')
                prototype=cls.base_fields[native_name]
                if choices and isinstance(prototype,forms.ChoiceField):
                    if isinstance(prototype,forms.ModelChoiceField):self.add_error('options','گزینه‌های این ورودی از فهرست مرجع می‌آیند؛ آنها را در بخش مربوط ویرایش کنید.')
                    else:
                        allowed={str(value) for value,label in prototype.choices if not isinstance(label,(list,tuple))}
                        if any(item['value'] not in allowed for item in choices):self.add_error('options','مقدار جدید برای وضعیت اصلی معتبر نیست؛ برای گزینه‌های مستقل، فیلد سفارشی بسازید.')
                if data.get('default_value'):
                    validator=deepcopy(cls.base_fields[native_name])
                    if isinstance(validator,forms.ChoiceField) and not isinstance(validator,forms.ModelChoiceField):
                        from .behavior_service import effective_options
                        validator.choices=[('', 'انتخاب کنید…')]+[(option['key'],option['label']) for option in effective_options(self.section,native_name,validator)]
                    try:validator.clean(data['default_value'])
                    except ValidationError as error:self.add_error('default_value',error)
        if data.get('minimum') is not None and data.get('maximum') is not None and data['minimum']>data['maximum']:self.add_error('maximum','حداکثر نباید کمتر از حداقل باشد.')
        if data.get('max_length') and data['max_length']>50000:self.add_error('max_length','حداکثر طول مجاز ۵۰۰۰۰ است.')
        for key in ('field_type','required','minimum','maximum','max_length','default_value'):
            if key in data:setattr(self.instance,key,data[key])
        self.instance.choices=choices
        if data.get('default_value') and not native_name:
            validator=typed_field(self.instance)
            if data.get('field_type')=='choice':
                from .behavior_service import effective_options
                validator.choices=[('', 'انتخاب کنید…')]+[(option['key'],option['label']) for option in effective_options(self.section,'extra_'+self.instance.key,validator)]
            try:validator.clean(data['default_value'])
            except forms.ValidationError as error:self.add_error('default_value',error)
        return data
    def save(self,commit=True):
        instance=super().save(commit=False)
        instance.choices=[]
        for line in self.cleaned_data.get('options','').splitlines():
            if line.strip():
                parts=line.split('|',1);instance.choices.append({'value':parts[0].strip(),'label':parts[-1].strip()})
        if commit:instance.save()
        return instance


class ColumnForm(Styled,forms.ModelForm):
    source=forms.ChoiceField(label='داده ستون')
    revision=forms.IntegerField(widget=forms.HiddenInput,required=False)
    class Meta:
        model=SectionColumn
        fields=['label','component_key','source','enabled','position','width','align','display','wrap','filterable','searchable','revision']
    def __init__(self,*args,section,**kwargs):
        super().__init__(*args,**kwargs)
        self.instance.section=section
        self.fields['source'].choices=[('','انتخاب داده ستون…')]+source_choices(section)
        from .interface import catalog
        from .structure_registry import component_scopes
        self.fields['component_key']=forms.ChoiceField(label='ستون موجود یا ستون جدید',required=False,choices=[('','افزودن ستون جدید')]+[(key,value['label']) for key,value in catalog().items() if value['kind']=='column' and section.key in component_scopes(key,value)])
        self.style()
    def clean_component_key(self):
        key=self.cleaned_data.get('component_key','')
        if key and self.instance.section.columns.filter(component_key=key).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('برای این ستون، تنظیم دیگری وجود دارد؛ همان تنظیم را ویرایش کنید.')
        return key
    def clean_width(self):
        width=self.cleaned_data['width']
        if not 60<=width<=800:raise forms.ValidationError('عرض باید بین ۶۰ تا ۸۰۰ پیکسل باشد.')
        return width


class StageForm(Styled,forms.ModelForm):
    assignee_role=forms.ChoiceField(label='نقش مسئول خودکار',choices=[('','مالک رکورد')]+list(ROLE_DISPLAY.items()),required=False)
    required_fields=forms.MultipleChoiceField(label='اطلاعات لازم در این مرحله',required=False)
    revision=forms.IntegerField(widget=forms.HiddenInput,required=False)
    class Meta:
        model=SectionStage
        fields=['label','position','enabled','initial','status','assignee_role','assignee','create_task','required_fields','revision']
        labels={'status':'وضعیت این مرحله','assignee':'کاربر مسئول مشخص'}
    def __init__(self,*args,section,**kwargs):
        super().__init__(*args,**kwargs);self.instance.section=section;self.section=section
        self.fields['required_fields'].choices=[(field.key,field.label) for field in section.fields.filter(enabled=True,native_name='')]
        self.fields['assignee'].queryset=self.fields['assignee'].queryset.filter(is_active=True)
        self.style()
    def clean(self):
        data=super().clean()
        if data.get('initial') and self.section.stages.filter(initial=True,enabled=True).exclude(pk=self.instance.pk).exists():self.add_error('initial','مرحله شروع دیگری فعال است؛ ابتدا آن را تغییر دهید.')
        if data.get('assignee') and data.get('assignee_role'):self.add_error('assignee','کاربر مشخص یا نقش را انتخاب کنید، نه هر دو.')
        return data


class TransitionForm(Styled,forms.ModelForm):
    roles=forms.MultipleChoiceField(label='نقش‌های مجاز برای این اقدام',choices=list(ROLE_DISPLAY.items()),required=False)
    revision=forms.IntegerField(widget=forms.HiddenInput,required=False)
    class Meta:
        model=SectionTransition
        fields=['label','source','target','roles','require_note','enabled','revision']
        labels={'source':'مرحله مبدأ','target':'مرحله مقصد'}
    def __init__(self,*args,section,**kwargs):
        super().__init__(*args,**kwargs);self.instance.section=section
        self.fields['source'].queryset=section.stages.all();self.fields['target'].queryset=section.stages.all();self.style()
    def clean(self):
        data=super().clean()
        if data.get('source') and data.get('source')==data.get('target'):self.add_error('target','مبدأ و مقصد متفاوت باشند.')
        return data
