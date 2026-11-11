"""Declarative form behavior shared by entry forms and the visual designer."""
from copy import deepcopy
from decimal import Decimal,InvalidOperation
from django import forms
from django.core.exceptions import ValidationError
from django.utils.module_loading import import_string
from .structure_registry import SECTIONS
from .structure_service import typed_field,choice_pairs,serialized
from .permissions import get_user_role

# Identity, ownership, access and credentials are never rewritten by a form rule.
LOCKED={'id','pk','name','mobile','username','password','password1','password2','user','employee','customer','assigned_user','assigned_to','role','permission','is_superuser','is_staff','is_interviewer'}


def prototypes(section):
    fields={}
    for path in SECTIONS.get(section.key,{}).get('forms',[]):
        for name,field in import_string(path).base_fields.items():
            if not name.startswith('password') and not isinstance(field.widget,forms.HiddenInput):fields[name]=deepcopy(field)
    if section.pk:
        for definition in section.fields.all():
            if not definition.native_name and definition.enabled:fields['extra_'+definition.key]=typed_field(definition)
    return fields


def empty_locked(section):
    result=set(LOCKED)
    for path in SECTIONS.get(section.key,{}).get('forms',[]):
        cls=import_string(path);model=getattr(getattr(cls,'_meta',None),'model',None)
        if model:
            for name in cls.base_fields:
                try:field=model._meta.get_field(name)
                except Exception:continue
                if not field.null and (not field.blank and not field.has_default() or field.choices and not field.blank or field.get_internal_type() in ('DecimalField','FloatField','IntegerField','PositiveIntegerField','SmallIntegerField','BigIntegerField','DateField','DateTimeField','TimeField','DurationField','UUIDField')):result.add(name)
    return result


def base_options(field):
    if not isinstance(field,forms.ChoiceField) or isinstance(field,forms.ModelChoiceField):return []
    return [{'key':str(value),'label':str(label),'base_value':str(value),'enabled':True,'position':index*10,'builtin':True}
            for index,(value,label) in enumerate(field.choices) if value!='' and not isinstance(label,(tuple,list))]


def effective_options(section,name,field,include_disabled=False):
    options={item['key']:item for item in base_options(field)}
    if not options and not isinstance(field,forms.ChoiceField):return []
    for item in section.options.all():
        if item.field_name==name:
            options[item.key]={'key':item.key,'label':item.label,'base_value':item.base_value or item.key,'enabled':item.enabled,'position':item.position,'builtin':item.key in options,'pk':item.pk,'revision':item.revision}
    result=sorted(options.values(),key=lambda item:(item['position'],item['key']))
    return result if include_disabled else [item for item in result if item['enabled']]


def normalize(value):
    if value is None:return ''
    if value is True:return 'true'
    if value is False:return 'false'
    if isinstance(value,(list,tuple)):return ','.join(normalize(v) for v in value)
    return str(value).strip().translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩','01234567890123456789'))


def matches(rule,values):
    current=normalize(values.get(rule['source']))
    expected=normalize(rule.get('value',''))
    operator=rule['operator']
    if operator=='equals':return current==expected
    if operator=='not_equals':return current!=expected
    if operator=='filled':return current not in ('','false')
    if operator=='empty':return current in ('','false')
    if operator=='contains':return expected in [normalize(item) for item in values.get(rule['source'],[])] if isinstance(values.get(rule['source']),(list,tuple)) else expected in current
    if operator=='in':
        allowed=[s.strip() for s in expected.split(',')]
        return any(normalize(item) in allowed for item in values.get(rule['source'],[])) if isinstance(values.get(rule['source']),(list,tuple)) else current in allowed
    try:
        a,b=Decimal(current),Decimal(expected)
        if not a.is_finite() or not b.is_finite():return False
        return a>b if operator=='gt' else a<b if operator=='lt' else False
    except (InvalidOperation,ValueError):return False


def evaluate(values,rules):
    values=deepcopy(values);seen=set()
    for turn in range(16):
        before=repr(sorted((key,normalize(value)) for key,value in values.items()))
        for rule in rules:
            if matches(rule,values) and rule['action'] in ('set','clear'):
                values[rule['target']]=([v.strip() for v in rule.get('argument','').split(',') if v.strip()] if rule.get('multiple') else rule.get('argument','')) if rule['action']=='set' else ([] if rule.get('multiple') else '')
        after=repr(sorted((key,normalize(value)) for key,value in values.items()))
        if before==after:break
        if after in seen:raise ValidationError('قواعد تغییر مقدار حلقه ایجاد کرده‌اند؛ مسئول تنظیمات باید مسیر قواعد را اصلاح کند.')
        seen.add(after)
    else:raise ValidationError('زنجیره قواعد فرم بیش از حد طولانی است.')
    states={};tags=[];remove_tags=[];messages=[];matched=[]
    for rule in rules:
        action,target=rule['action'],rule.get('target','')
        state=states.setdefault(target,{}) if target else {}
        if action=='show':state.setdefault('visible',False)
        if not matches(rule,values):continue
        matched.append(str(rule['id']))
        if action in ('show','hide'):state['visible']=action=='show'
        elif action in ('require','optional'):state['required']=action=='require'
        elif action=='choices':state['choices']=[v.strip() for v in rule['argument'].split(',') if v.strip()]
        elif action=='clear':state['clear']=True
        elif action in ('add_tag','remove_tag'):
            bucket=tags if action=='add_tag' else remove_tags
            if rule['argument'] not in bucket:bucket.append(rule['argument'])
        elif action in ('popup','notice'):messages.append({'id':str(rule['id']),'kind':action,'target':target,'text':rule['argument'],'source':rule['source']})
    return {'values':values,'states':states,'tags':tags,'remove_tags':remove_tags,'messages':messages,'matched':matched}


def rule_payload(section,names,user=None):
    role=get_user_role(user) if user and user.is_authenticated else None
    return [{'id':str(rule.pk),'label':rule.label,'source':rule.source,'operator':rule.operator,'value':rule.value,
             'action':rule.action,'target':rule.target,'argument':rule.argument,'position':rule.position}
            for rule in section.behaviors.all() if rule.enabled and rule.source in names and
            (not rule.target or rule.target in names) and (not rule.roles or role in rule.roles)]


def configure_behavior(form,section,user=None):
    """Run before Django field cleaning; final native form validation still runs."""
    maps={};configured=False
    empty_protected=empty_locked(section)
    for name,field in form.fields.items():
        if not isinstance(field,forms.ChoiceField) or isinstance(field,forms.ModelChoiceField):continue
        if any(option.field_name==name for option in section.options.all()):
            if not hasattr(field,'_behavior_original_clean'):
                field._behavior_original_clean=field.clean
                field._behavior_original_choices=list(field.choices)
            original=deepcopy(field)
            original.choices=field._structure_original_choices if hasattr(field,'_structure_original_choices') else field._behavior_original_choices
            options=effective_options(section,name,original)
            canonical={str(value) for value,label in original.choices if not isinstance(label,(tuple,list))}
            # Removing an option from a reference/role-specific form never restores it.
            options=[item for item in options if item['base_value'] in canonical or name.startswith('extra_')]
            meta=getattr(form,'_structure_record',None) or getattr(form,'record',None)
            selection=meta.data.get('_selected_options',{}).get(name) if meta else None
            current=form.initial.get(name)
            if isinstance(field,forms.MultipleChoiceField):
                current_values=[str(value) for value in (current or [])]
                selections=selection if isinstance(selection,list) else []
                all_options=effective_options(section,name,original,True)
                picked=[]
                for index,current_value in enumerate(current_values):
                    stored=next((item for item in all_options if index<len(selections) and item['key']==selections[index] and item['base_value']==current_value and current_value in canonical),None)
                    selected=stored or next((item for item in options if item['key']==current_value or item['base_value']==current_value),None)
                    if selected:
                        if not any(item['key']==selected['key'] for item in options):options.append({**selected,'label':selected['label']+' (انتخاب قبلی)'})
                        picked.append(selected['key'])
                    else:
                        options.append({'key':current_value,'label':current_value+' (انتخاب قبلی)','base_value':current_value});picked.append(current_value)
                form.initial[name]=picked
            selected_option=next((item for item in effective_options(section,name,original,True) if item['key']==selection),None)
            if not isinstance(field,forms.MultipleChoiceField) and selected_option and (name.startswith('extra_') and str(current)==selection or selected_option['base_value']==str(current)) and (name.startswith('extra_') or selected_option['base_value'] in canonical):
                if not any(item['key']==selection for item in options):options.append({**selected_option,'label':selected_option['label']+' (انتخاب قبلی)'})
                current=selection;form.initial[name]=selection
            previous=getattr(form,'instance',None) or getattr(form,'record',None)
            if not isinstance(field,forms.MultipleChoiceField) and previous is not None and getattr(previous,'pk',None) and current not in (None,'') and not any(item['key']==str(current) for item in options):
                matching=next((item for item in options if item['base_value']==str(current)),None)
                if matching:form.initial[name]=matching['key']
                else:
                    label=dict((str(value),str(label)) for value,label in original.choices if not isinstance(label,(tuple,list))).get(str(current),str(current))
                    options.append({'key':str(current),'base_value':str(current),'label':label+' (انتخاب قبلی)'})
            field.choices=[('','انتخاب کنید…')]+[(item['key'],item['label']) for item in options]
            maps[name]={item['key']:item['base_value'] for item in options};configured=True
            if not name.startswith('extra_'):
                original_clean=field._behavior_original_clean;mapping=maps[name]
                def clean_choice(value,_clean=original_clean,_mapping=mapping):
                    result=_clean(value)
                    return [_mapping.get(item,item) for item in result] if isinstance(result,(list,tuple)) else _mapping.get(result,result)
                field.clean=clean_choice
    names={name for name,field in form.fields.items() if not field.disabled}
    rules=[rule for rule in rule_payload(section,names,user) if not (rule['target'] in empty_protected and rule['action'] in ('hide','optional','clear'))]
    for rule in rules:rule['multiple']=isinstance(form.fields.get(rule['target']),forms.MultipleChoiceField)
    form._behavior_mapped_names={name for name in maps if not name.startswith('extra_')}
    form.structure_replace_logic=section.replace_form_logic
    form.structure_behavior_payload={'rules':rules,'replace':section.replace_form_logic,'option_maps':maps,
                                    'locked':sorted(LOCKED),'empty_locked':sorted(empty_protected),'multiple':[name for name,field in form.fields.items() if isinstance(field,forms.MultipleChoiceField)],'required_fields':[name for name,field in form.fields.items() if field.required],'booleans':[name for name,field in form.fields.items() if isinstance(field,forms.BooleanField)],'fields':list(form.fields)}
    for name,field in form.fields.items():
        field.widget.attrs['data-behavior-name']=name
    if not form.is_bound:return
    raw={name:(form.data.getlist(name) if hasattr(form.data,'getlist') and isinstance(field,forms.MultipleChoiceField) else form.data.get(name,False if isinstance(field,forms.BooleanField) else '')) for name,field in form.fields.items()}
    for name,field in form.fields.items():
        if isinstance(field,forms.BooleanField):raw[name]=field.widget.value_from_datadict(form.data,getattr(form,'files',{}),name)
    try:result=evaluate(raw,rules)
    except ValidationError as error:form._behavior_error=error;return
    data=form.data.copy()
    for name,val in result['values'].items():
        if name in LOCKED or form.fields[name].disabled:continue
        if isinstance(val,(list,tuple)) and hasattr(data,'setlist'):data.setlist(name,list(val))
        else:data[name]=val
    for name,state in result['states'].items():
        if name not in form.fields or name in LOCKED:continue
        field=form.fields[name]
        if field.disabled:continue
        if 'required' in state:field.required=state['required']
        if state.get('visible') is False:
            field.required=False;field.disabled=True;field.widget.attrs['data-behavior-managed-disabled']='true'
            if any(rule['target']==name and rule['action'] in ('set','clear') and str(rule['id']) in result['matched'] for rule in rules):
                form.initial[name]=result['values'].get(name,'');field.initial=form.initial[name]
        if state.get('clear'):
            field.initial='';form.initial[name]=''
        if 'choices' in state and isinstance(field,forms.ChoiceField) and not isinstance(field,forms.ModelChoiceField):
            field.choices=[(value,label) for value,label in field.choices if str(value) in state['choices'] or value=='']
    form.data=data;form._behavior_result=result;form._behavior_option_maps=maps
    form._behavior_selections={name:([normalize(item) for item in result['values'].get(name,[])] if isinstance(form.fields[name],forms.MultipleChoiceField) else normalize(result['values'].get(name))) for name in maps if not form.fields[name].disabled}


def canonicalize(form):
    for name,mapping in getattr(form,'_behavior_option_maps',{}).items():
        if name in form.cleaned_data and name not in LOCKED and name not in getattr(form,'_behavior_mapped_names',set()):
            value=form.cleaned_data[name]
            if value in mapping and not name.startswith('extra_'):form.cleaned_data[name]=mapping[value]


def behavior_values(form):
    result=getattr(form,'_behavior_result',{})
    if not result.get('tags') and not result.get('remove_tags') and not getattr(form,'_behavior_selections',{}):return {}
    previous=getattr(form,'_structure_record',None) or getattr(form,'record',None)
    tags=list(previous.data.get('_behavior_tags',[])) if previous else []
    tags=[label for label in tags if label not in result.get('remove_tags',[])]
    for label in result.get('tags',[]):
        if label not in tags:tags.append(label)
    return {'_behavior_tags':tags,'_selected_options':{**(previous.data.get('_selected_options',{}) if previous else {}),**getattr(form,'_behavior_selections',{})}}
