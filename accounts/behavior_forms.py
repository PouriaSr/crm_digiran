from copy import deepcopy
from django import forms
from django.core.exceptions import ValidationError
from .models import SectionBehavior,SectionOption
from .permissions import ROLE_DISPLAY
from .structure_forms import Styled
from .behavior_service import prototypes,base_options,effective_options,LOCKED,empty_locked


class BehaviorForm(Styled,forms.ModelForm):
    roles=forms.MultipleChoiceField(label='فقط برای این نقش‌ها',choices=list(ROLE_DISPLAY.items()),required=False)
    revision=forms.IntegerField(widget=forms.HiddenInput,required=False)
    argument_choices=forms.MultipleChoiceField(label='گزینه‌های انتخاب‌شده',choices=[],required=False)
    class Meta:
        model=SectionBehavior
        fields=['label','source','operator','value','action','target','argument','roles','enabled','position','revision']
    def __init__(self,*args,section,actor=None,**kwargs):
        super().__init__(*args,**kwargs);self.section=section;self.instance.section=section;self.prototypes=prototypes(section)
        choices=[(name,str(field.label or name)) for name,field in self.prototypes.items()]
        self.fields['source']=forms.ChoiceField(label='وقتی ورودی',choices=choices)
        self.fields['target']=forms.ChoiceField(label='ورودی مقصد',choices=[('','بدون ورودی مقصد')]+choices,required=False)
        self.fields['value'].help_text='مقدار ذخیره‌شده گزینه؛ برای شرط «یکی از» مقدارها را با کاما جدا کنید.'
        self.fields['argument'].help_text='برای محدودکردن گزینه‌ها، شناسه گزینه‌ها را با کاما جدا کنید.'
        self.fields['argument'].widget=forms.Textarea(attrs={'rows':3})
        source=self.data.get('source') if self.is_bound else self.initial.get('source') or self.instance.source
        operator=self.data.get('operator') if self.is_bound else self.initial.get('operator') or self.instance.operator
        prototype=self.prototypes.get(source)
        from .structure_service import can_access
        if isinstance(prototype,forms.ModelChoiceField) and actor and can_access(actor,section) and operator in ('equals','not_equals'):
            self.fields['value']=forms.ModelChoiceField(label='گزینه شرط',queryset=prototype.queryset,required=False,empty_label='انتخاب کنید…')
        target_name=self.data.get('target') if self.is_bound else self.initial.get('target') or self.instance.target
        target_field=self.prototypes.get(target_name)
        self.fields['argument_choices'].choices=[(item['key'],item['label']) for item in effective_options(section,target_name,target_field)] if target_field else []
        self.initial['argument_choices']=[value.strip() for value in self.instance.argument.split(',') if value.strip()]
        self.fields['label'].required=False
        self.style()
    def clean(self):
        data=super().clean();action=data.get('action');target=data.get('target');argument=data.get('argument','').strip()
        if action=='choices' or action=='set' and isinstance(self.prototypes.get(target),forms.MultipleChoiceField):
            if data.get('argument_choices'):argument=','.join(data['argument_choices']);data['argument']=argument
        if isinstance(self.fields['value'],forms.ModelChoiceField) and data.get('value') is not None:data['value']=str(data['value'].pk)
        if not data.get('label'):
            data['label']=(str(self.prototypes.get(data.get('source'),'ورودی'))+' ← '+dict(SectionBehavior.ACTIONS).get(action,''))[:180]
            if data.get('source') in self.prototypes:data['label']=(str(self.prototypes[data['source']].label)+' ← '+dict(SectionBehavior.ACTIONS).get(action,''))[:180]
        if action in ('show','hide','require','optional','set','clear','choices') and not target:self.add_error('target','ورودی مقصد را انتخاب کنید.')
        if action in ('add_tag','remove_tag','popup','notice','set','choices') and not argument:self.add_error('argument','مقدار یا متن این اقدام را وارد کنید.')
        if target in empty_locked(self.section) and action in ('hide','optional','clear'):self.add_error('target','این ورودی برای هویت یا ساختار داده اصلی ضروری است؛ پنهان یا خالی نمی‌شود.')
        if target in LOCKED and action in ('hide','optional','set','clear','choices'):self.add_error('target','شناسه، مالکیت و دسترسی اشخاص را از قواعد فرم تغییر ندهید.')
        if action in ('add_tag','remove_tag') and len(argument)>80:self.add_error('argument','عنوان برچسب حداکثر ۸۰ نویسه باشد.')
        field=self.prototypes.get(target)
        if action=='set' and field:
            if isinstance(field,forms.ModelChoiceField):self.add_error('target','برای انتخاب از فهرست مرجع، پنجره انتخاب بسازید.')
            else:
                validator=deepcopy(field);validator.required=False
                if isinstance(field,forms.ChoiceField):validator.choices=[(item['key'],item['label']) for item in effective_options(self.section,target,field)]
                try:validator.clean([v.strip() for v in argument.split(',') if v.strip()] if isinstance(field,forms.MultipleChoiceField) else argument)
                except ValidationError as error:self.add_error('argument',error)
        if action=='choices' and field:
            allowed={item['key'] for item in effective_options(self.section,target,field)}
            if not allowed:self.add_error('target','این ورودی فهرست گزینه مستقل ندارد.')
            elif any(key.strip() not in allowed for key in argument.split(',')):self.add_error('argument','شناسه گزینه در این ورودی وجود ندارد.')
        if action in ('set','clear') and target and data.get('enabled'):
            graph={}
            for rule in self.section.behaviors.exclude(pk=self.instance.pk).filter(enabled=True,action__in=['set','clear']):graph.setdefault(rule.source,set()).add(rule.target)
            graph.setdefault(data.get('source'),set()).add(target)
            def visit(node,path):
                if node in path:return True
                return any(visit(next_node,path|{node}) for next_node in graph.get(node,()))
            if any(visit(node,set()) for node in graph):self.add_error('target','این تغییر، حلقه تغییر مقدار می‌سازد؛ مسیر قواعد را اصلاح کنید.')
        return data


class OptionForm(Styled,forms.ModelForm):
    revision=forms.IntegerField(widget=forms.HiddenInput,required=False)
    class Meta:
        model=SectionOption
        fields=['label','key','base_value','enabled','position','revision']
    def __init__(self,*args,section,field_name,**kwargs):
        super().__init__(*args,**kwargs);self.instance.section=section;self.instance.field_name=field_name
        self.prototype=prototypes(section).get(field_name)
        choices=base_options(self.prototype) if self.prototype else []
        native=not field_name.startswith('extra_')
        self.fields['base_value']=forms.ChoiceField(label='رفتار پایه در فرآیند اصلی',required=native,choices=[('','گزینه مستقل')]+[(item['key'],item['label']) for item in choices])
        self.fields['base_value'].help_text='گزینه جدید می‌تواند عنوان و قواعد مستقل داشته باشد؛ رفتار پایه مسیر ذخیره در فرآیند اصلی را مشخص می‌کند.'
        if self.instance.pk:self.fields['key'].disabled=True
        self.style()
    def clean_key(self):
        key=self.cleaned_data['key']
        if key.startswith('_'):raise forms.ValidationError('شناسه با حرف یا عدد شروع شود.')
        return key
