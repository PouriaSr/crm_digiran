"""Connect configured fields to the real Django form validation/save lifecycle."""
from functools import wraps
from django import forms
from django.db.models.signals import post_save
from django.core.validators import MaxLengthValidator, MinValueValidator, MaxValueValidator
from .structure_registry import scope_for_request
from .structure_service import schema,fields_for,typed_field,serialized,save_record,choice_pairs

PROTECTED={'id','pk','name','mobile','username','password','password1','password2','code','customer','employee','assigned_user','source','call_type','purpose','call_status','customer_analysis','requested_condition'}


def configure_form(cls, scopes):
    original=cls.__init__
    @wraps(original)
    def init(self,*args,**kwargs):
        explicit=kwargs.pop('structure_scope',None)
        original(self,*args,**kwargs)
        from crm.middleware import get_current_request
        request=get_current_request()
        key=explicit or (scope_for_request(request) if request else None)
        if key not in scopes:return
        section=schema(key,request)
        if not section or not section.enabled:return
        actor=getattr(request,'user',None)
        self.structure_section,self.structure_actor=section,actor
        self.structure_definitions=fields_for(section,actor)
        self.structure_extra_names=[]
        instance=getattr(self,'instance',None)
        stored=None
        if cls.__name__=='HubCallForm' and self.is_bound:
            from customers.models import Customer
            from crm.duplicate_check import normalize_digits
            instance=Customer.objects.filter(mobile=normalize_digits(self.data.get('mobile',''))).first()
        anchor=instance.application if key=='hiring' and getattr(instance,'application_id',None) else instance
        if anchor is not None and anchor.pk:
            from django.contrib.contenttypes.models import ContentType
            stored=section.records.filter(content_type=ContentType.objects.get_for_model(anchor),object_id=anchor.pk).select_related('stage').first()
        self._structure_record=stored
        self._structure_anchor=anchor
        for item in self.structure_definitions:
            if item.native_name:
                if item.native_name not in self.fields:continue
                field=self.fields[item.native_name]
                if field.disabled:continue
                field.label=item.label;field.help_text=item.help_text
                field.widget.attrs['placeholder']=item.placeholder
                if item.native_name not in PROTECTED:
                    model=getattr(getattr(self,'_meta',None),'model',None)
                    try:native=model._meta.get_field(item.native_name) if model else None
                    except Exception:native=None
                    hard_required=bool(native and not native.null and not native.blank and not native.has_default() and not item.default_value)
                    field.required=item.required or hard_required
                    if item.readonly and (getattr(instance,'pk',None) or item.default_value):field.disabled=True
                    if not item.enabled and not field.required:
                        field.widget=forms.HiddenInput();field.disabled=True
                    if item.default_value and not getattr(instance,'pk',None):self.initial.setdefault(item.native_name,item.default_value)
                if item.max_length and isinstance(field,forms.CharField):field.validators.append(MaxLengthValidator(item.max_length))
                if isinstance(field,(forms.IntegerField,forms.DecimalField,forms.FloatField)):
                    if item.minimum is not None:field.validators.append(MinValueValidator(item.minimum))
                    if item.maximum is not None:field.validators.append(MaxValueValidator(item.maximum))
                if item.choices and isinstance(field,forms.ChoiceField) and not isinstance(field,forms.ModelChoiceField):
                    available={str(value):label for value,label in field.choices if not isinstance(label,(list,tuple))}
                    field.choices=[(value,label) for value,label in choice_pairs(item) if value in available]
                field.widget.attrs['data-structure-order']=item.position
                field.widget.attrs['data-structure-label']=item.label
                if not item.enabled and not field.required:field.widget.attrs['data-structure-hide']='1'
                continue
            name='extra_'+item.key
            self.fields[name]=typed_field(item);self.structure_extra_names.append(name)
            if stored and item.key in stored.data:self.initial[name]=stored.data[item.key]
        # Existing fields retain their rendering contracts; extras get their own block.
    cls.__init__=init
    old_clean=cls.clean
    @wraps(old_clean)
    def clean(self):
        for item in getattr(self,'structure_definitions',[]):
            if item.native_name and item.default_value and self.cleaned_data.get(item.native_name) in (None,'') and item.native_name in self.fields:
                self.cleaned_data[item.native_name]=self.fields[item.native_name].clean(item.default_value)
        extras={key:value for key,value in self.cleaned_data.items() if key.startswith('extra_')}
        result=old_clean(self)
        if result is not None:result.update(extras)
        section=getattr(self,'structure_section',None)
        if section:
            stored=getattr(self,'_structure_record',None)
            anchor=getattr(self,'_structure_anchor',None)
            if section.gate_save and anchor is not None and anchor.pk and (not stored or not stored.stage_id or stored.stage.status!='done'):
                raise forms.ValidationError('ابتدا گردش‌کار این بخش را در اطلاعات تکمیلی و مراحل تکمیل کنید.')
            initial=next((stage for stage in section.stages.all() if stage.initial and stage.enabled),None)
            if initial:
                for key in initial.required_fields:
                    name='extra_'+key
                    if self.cleaned_data.get(name) in (None,'') and name in self.fields:self.add_error(name,'این مقدار برای شروع فرآیند لازم است.')
        return result
    cls.clean=clean
    if issubclass(cls,forms.ModelForm):
        original_save=cls.save
        @wraps(original_save)
        def save(self,*args,**kwargs):
            pending=extra_values(self)
            if pending or hasattr(self,'structure_section') and any(stage.initial and stage.enabled for stage in self.structure_section.stages.all()):self.instance._structure_pending=(self.structure_section,pending,self.structure_actor)
            return original_save(self,*args,**kwargs)
        cls.save=save
    return cls


def extra_values(form):
    return {item.key:serialized(form.cleaned_data.get('extra_'+item.key)) for item in getattr(form,'structure_definitions',[]) if not item.native_name and 'extra_'+item.key in form.cleaned_data}


def save_form_extras(form,subject):
    values=extra_values(form)
    section=getattr(form,'structure_section',None)
    if section and (values or any(stage.initial and stage.enabled for stage in section.stages.all())):
        actor=getattr(form,'structure_actor',None)
        save_record(form.structure_section,values,actor,subject=subject,trusted=True)


def save_pending(sender,instance,raw=False,**kwargs):
    if raw:return
    pending=getattr(instance,'_structure_pending',None)
    if pending:
        del instance._structure_pending
        section,values,actor=pending
        subject=instance.application if section.key=='hiring' and getattr(instance,'application_id',None) else instance
        save_record(section,values,actor,subject=subject,trusted=True)


post_save.connect(save_pending,dispatch_uid='accounts.structure_form_save',weak=False)
