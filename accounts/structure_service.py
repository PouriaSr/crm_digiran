"""Typed, scoped data and explicit workflow transitions; no evaluated code/SQL."""
from datetime import date
from decimal import Decimal
from django import forms
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError, ObjectDoesNotExist
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import SectionSchema, SectionField, SectionRecord, SectionRecordEvent, SectionStage
from .permissions import get_user_role, has_permission
from .structure_registry import SECTIONS, scope_for_request


def all_schemas(request=None):
    if request is None:
        from crm.middleware import get_current_request
        request=get_current_request()
    if request is not None and hasattr(request,'_section_schemas'):return request._section_schemas
    from django.db.models import Exists,OuterRef
    from .models import SectionColumn,SectionTransition
    items=SectionSchema.objects.order_by('position','pk').annotate(_has_fields=Exists(SectionField.objects.filter(section_id=OuterRef('pk'))),
        _has_columns=Exists(SectionColumn.objects.filter(section_id=OuterRef('pk'))),
        _has_stages=Exists(SectionStage.objects.filter(section_id=OuterRef('pk'))),
        _has_transitions=Exists(SectionTransition.objects.filter(section_id=OuterRef('pk'))))
    result={item.key:item for item in items}
    if request is not None:request._section_schemas=result
    return result


def schema(key, request=None):
    item=all_schemas(request).get(key)
    if item and not getattr(item,'_structure_prefetched',False):
        from django.db.models import prefetch_related_objects
        lookups=[]
        for name in ('fields','columns','stages','transitions'):
            if getattr(item,'_has_'+name):lookups.append(name)
            else:
                if not hasattr(item,'_prefetched_objects_cache'):item._prefetched_objects_cache={}
                item._prefetched_objects_cache[name]=getattr(item,name).none()
        if lookups:prefetch_related_objects([item],*lookups)
        item._structure_prefetched=True
    return item


def can_access(user, section, write=False):
    if not user or not user.is_authenticated or not section.enabled:return False
    definition=SECTIONS.get(section.key)
    permission=definition['write' if write else 'read'] if definition else section.permission
    return bool((not permission or has_permission(user,permission)) and (not section.permission or has_permission(user,section.permission)) and
                (not section.roles or get_user_role(user) in section.roles))


def require_access(user, section, write=False):
    if not can_access(user,section,write):raise PermissionDenied


def fields_for(section,user=None):
    return [item for item in section.fields.all() if (item.enabled or item.native_name) and (not item.roles or user and get_user_role(user) in item.roles)]


def choice_pairs(item):
    return [(str(value.get('value','')),str(value.get('label',value.get('value','')))) if isinstance(value,dict) else (str(value),str(value)) for value in item.choices]


class ConfiguredDateField(forms.DateField):
    def to_python(self,value):
        if value in self.empty_values:return None
        if isinstance(value,date):return value
        from crm.numerals import normalize_input
        raw=normalize_input(str(value)).replace('-','/')
        try:
            year,month,day=map(int,raw.split('/'))
            if 1200<=year<1700:
                import jdatetime
                return jdatetime.date(year,month,day).togregorian()
            return date(year,month,day)
        except (TypeError,ValueError):raise ValidationError('تاریخ معتبر وارد کنید.')
    def prepare_value(self,value):
        if value in self.empty_values:return ''
        try:
            if not isinstance(value,date):value=date.fromisoformat(str(value))
            import jdatetime
            return jdatetime.date.fromgregorian(date=value).strftime('%Y/%m/%d')
        except ValueError:return value


def typed_field(item):
    common={'label':item.label,'required':item.required,'help_text':item.help_text,'initial':item.default_value or None,'disabled':item.readonly}
    widget_attrs={'placeholder':item.placeholder,'class':'w-full border rounded-xl p-3','data-structure-field':item.key}
    if item.field_type=='longtext':field=forms.CharField(max_length=item.max_length or 10000,widget=forms.Textarea(attrs={**widget_attrs,'rows':3}),**common)
    elif item.field_type=='integer':field=forms.IntegerField(min_value=item.minimum,max_value=item.maximum,**common)
    elif item.field_type=='decimal':field=forms.DecimalField(max_digits=20,decimal_places=4,min_value=item.minimum,max_value=item.maximum,**common)
    elif item.field_type=='date':
        field=ConfiguredDateField(widget=forms.TextInput(attrs={'data-jdp':'','autocomplete':'off'}),**common)
    elif item.field_type=='boolean':field=forms.BooleanField(**common)
    elif item.field_type=='choice':field=forms.ChoiceField(choices=[('','انتخاب کنید…')]+choice_pairs(item),**common)
    elif item.field_type=='email':field=forms.EmailField(max_length=item.max_length or 254,**common)
    elif item.field_type=='url':field=forms.URLField(max_length=item.max_length or 500,**common)
    else:field=forms.CharField(max_length=item.max_length or 500,**common)
    field.widget.attrs.update(widget_attrs)
    field.widget.attrs['id']='structure_'+item.key
    return field


def serialized(value):
    if isinstance(value,Decimal):return format(value.normalize(),'f')
    if isinstance(value,date):return value.isoformat()
    return value


class RecordForm(forms.Form):
    title=forms.CharField(label='عنوان',max_length=200,required=False)
    revision=forms.IntegerField(widget=forms.HiddenInput,required=False)
    def __init__(self,*args,section,user,record=None,**kwargs):
        self.section,self.actor,self.record=section,user,record
        super().__init__(*args,**kwargs)
        self.definitions=fields_for(section,user)
        if not section.custom:self.fields.pop('title')
        if record:self.initial.update({'revision':record.revision,'title':record.title})
        else:self.initial['revision']=0
        for item in self.definitions:
            if item.native_name:continue
            self.fields['extra_'+item.key]=typed_field(item)
            if record and item.key in record.data:self.initial['extra_'+item.key]=record.data[item.key]
    def clean(self):
        data=super().clean()
        stage=self.record.stage if self.record and self.record.stage_id else active_stage(self.section)
        if stage:
            for key in stage.required_fields:
                name='extra_'+key
                value=data.get(name,self.record.data.get(key) if self.record else None)
                if value in (None,''):
                    if name in self.fields:self.add_error(name,'این فیلد برای مرحله فعلی الزامی است.')
                    else:self.add_error(None,'اطلاعات لازم مرحله برای نقش شما قابل ویرایش نیست؛ به مسئول بخش مراجعه کنید.')
        return data

    def values(self):
        return {item.key:serialized(self.cleaned_data['extra_'+item.key]) for item in self.definitions if not item.native_name}


def native_visible(user, section, subject, edit=False):
    from customers.access import is_card_manager
    key=section.key
    if key=='info' and subject.is_interviewer and not has_permission(user,'customers.candidate_view'):return False
    if key=='registration' and subject.is_interviewer:return False
    if key=='case' and subject.customer.is_interviewer:return False
    if is_card_manager(user):return True
    if key=='info':return subject.assigned_to_id==user.pk if edit else not subject.is_interviewer or subject.assigned_to_id==user.pk or subject.created_by_id==user.pk
    if key=='registration':return subject.assigned_to_id==user.pk
    if key=='case':return subject.customer.assigned_to_id==user.pk
    if key=='hiring':return subject.reception.customer.assigned_to_id==user.pk
    if key=='tasks':return subject.assigned_user_id==user.pk or bool(subject.assigned_to_id and subject.assigned_to.user_id==user.pk)
    if key in ('calls','invoices','ads'):
        if key=='calls' and subject.customer_id:return subject.customer.assigned_to_id==user.pk
        owner=getattr(subject,'created_by_id',None) or getattr(subject,'called_by_id',None)
        return owner==user.pk
    return True


def native_subject(section,pk,user,write=False):
    from django.shortcuts import get_object_or_404
    definition=SECTIONS.get(section.key)
    if not definition:raise ValidationError('این بخش رکورد اصلی ندارد.')
    model=apps.get_model(definition['model'])
    subject=get_object_or_404(model._default_manager,pk=pk)
    if not native_visible(user,section,subject,write):raise PermissionDenied
    return subject


def record_access(user,record,write=False):
    require_access(user,record.section,write)
    from customers.access import is_card_manager
    if record.content_type_id:
        try:subject=record.content_type.get_object_for_this_type(pk=record.object_id)
        except ObjectDoesNotExist:raise PermissionDenied('رکورد اصلی دیگر در دسترس نیست.')
        customer=getattr(subject,'customer',None)
        if getattr(subject,'is_deleted',False) or customer and customer.is_deleted:raise PermissionDenied
        if record.section.key=='info' and getattr(subject,'is_interviewer',False) and not has_permission(user,'customers.candidate_view'):raise PermissionDenied
        if not native_visible(user,record.section,subject,write):
            from hr.models import Task
            if not Task.objects.filter(source_type='structure',source_id=record.pk,assigned_user=user).exists():raise PermissionDenied
    elif not is_card_manager(user) and record.owner_id!=user.pk:
        from hr.models import Task
        assigned=Task.objects.filter(source_type='structure',source_id=record.pk,assigned_user=user).exists()
        if not assigned:raise PermissionDenied


def native_owner(subject,fallback=None):
    from django.contrib.auth.models import User
    for name in ('assigned_user','assigned_to','created_by','called_by','user'):
        owner=getattr(subject,name,None)
        if isinstance(owner,User):return owner
        if owner is not None and isinstance(getattr(owner,'user',None),User):return owner.user
    customer=getattr(subject,'customer',None)
    if customer is not None:return getattr(customer,'assigned_to',None) or fallback
    reception=getattr(subject,'reception',None)
    if reception is not None:return reception.customer.assigned_to or fallback
    return fallback


def record_for_subject(section, subject, owner=None):
    content=ContentType.objects.get_for_model(subject)
    return SectionRecord.objects.get_or_create(section=section,content_type=content,object_id=subject.pk,
                defaults={'title':str(subject)[:200],'owner':native_owner(subject,owner)})[0]


def active_stage(section):
    return section.stages.filter(enabled=True,initial=True).order_by('position','pk').first()


def validate_stage(stage,data):
    required={field.key:field for field in stage.section.fields.filter(enabled=True,native_name='')}
    invalid=[]
    for key in stage.required_fields:
        field=required.get(key)
        if field is None:invalid.append(key);continue
        validator=typed_field(field);validator.required=True
        try:validator.clean(data.get(key))
        except ValidationError:invalid.append(field.label)
    if invalid:raise ValidationError('اطلاعات لازم مرحله معتبر یا کامل نیست: '+', '.join(invalid))


@transaction.atomic
def save_record(section, values, user, record=None, title='', revision=None, subject=None, trusted=False):
    if not trusted:require_access(user,section,True)
    if not trusted and subject and not native_visible(user,section,subject,True):raise PermissionDenied
    if subject and record is None:record=record_for_subject(section,subject,user)
    if record:
        record=SectionRecord.objects.select_for_update().get(pk=record.pk)
        if revision is not None and record.revision!=revision:raise ValidationError('رکورد هم‌زمان تغییر کرده؛ صفحه را تازه کنید.')
        before={'data':record.data.copy(),'stage':record.stage_id,'title':record.title}
    else:
        record=SectionRecord(section=section,owner=user,title=title,revision=0)
        before={}
    record.data={**record.data,**values}
    if title:record.title=title
    if not record.stage_id:record.stage=active_stage(section)
    if record.stage:
        validate_stage(record.stage,record.data)
    record.revision+=1;record.save()
    after={'data':record.data,'stage':record.stage_id,'title':record.title}
    if before!=after:
        SectionRecordEvent.objects.create(record=record,actor=user,before=before,after=after)
    sync_stage_task(record,user)
    return record


def sync_stage_task(record,actor=None):
    from hr.models import Task
    from hr.task_automation import sync
    if not record.stage_id:return
    stage=record.stage
    for task in Task.objects.filter(source_type='structure',source_id=record.pk).exclude(status__in=['done','cancelled']):
        if task.source_key!=f'structure:{record.pk}:{stage.pk}' or stage.status=='done' or not stage.create_task:
            task.status='done' if stage.status=='done' or task.source_key!=f'structure:{record.pk}:{stage.pk}' else 'cancelled';task.save()
    if not stage.create_task or stage.status=='done':return
    owner=stage.assignee or record.owner or actor
    if stage.assignee_role:
        from django.contrib.auth.models import User
        owner=next((user for user in User.objects.filter(is_active=True).prefetch_related('groups','permission_overrides')
                    if get_user_role(user)==stage.assignee_role and can_access(user,record.section,True) and has_permission(user,'hr.view_tasks')),None)
    if owner and (not owner.is_active or not can_access(owner,record.section,True) or not has_permission(owner,'hr.view_tasks')):owner=None
    customer=None
    if record.content_type_id:
        subject=record.content_type.get_object_for_this_type(pk=record.object_id)
        from customers.models import Customer
        customer=subject if isinstance(subject,Customer) else getattr(subject,'customer',None)
        if customer is None and hasattr(subject,'reception'):customer=subject.reception.customer
    if owner and customer and customer.is_interviewer and record.section.key=='info' and not has_permission(owner,'customers.candidate_view'):owner=None
    if record.archived or customer and customer.is_deleted:
        Task.objects.filter(source_type='structure',source_id=record.pk).exclude(status__in=['done','cancelled']).update(status='cancelled')
        return
    sync(f'structure:{record.pk}:{stage.pk}','structure',record,stage.label+' — '+(record.title or record.section.label),owner,
         stage.status,customer=customer,description='مرحله قابل تنظیم «'+record.section.label+'»؛ اطلاعات و نتیجه را در صفحه همین رکورد ثبت کنید.',allow_unassigned=True)


@transaction.atomic
def transition_record(record, transition, user, revision, note=''):
    record=SectionRecord.objects.select_for_update().select_related('section','stage').get(pk=record.pk)
    record_access(user,record,True)
    if record.revision!=revision:raise ValidationError('این رکورد تغییر کرده؛ صفحه را تازه کنید.')
    if transition.section_id!=record.section_id or transition.source_id!=record.stage_id or not transition.enabled or not transition.target.enabled:raise ValidationError('این انتقال برای مرحله فعلی مجاز نیست.')
    if transition.roles and get_user_role(user) not in transition.roles:raise PermissionDenied
    if transition.require_note and not note.strip():raise ValidationError('توضیح انجام اقدام الزامی است.')
    validate_stage(transition.target,record.data)
    before={'stage':record.stage_id}
    record.stage=transition.target;record.revision+=1;record.save(update_fields=['stage','revision','updated_at'])
    SectionRecordEvent.objects.create(record=record,actor=user,before=before,after={'stage':record.stage_id},note=note.strip())
    sync_stage_task(record,user)
    return record


def structure_context(request):
    if not request.user.is_authenticated:return {}
    from .structure_registry import scope_for_request
    key=scope_for_request(request)
    current=schema(key,request) if key else None
    if current and not can_access(request.user,current):current=None
    filters=getattr(request,'_structure_filter_form',None)
    preserved=[(key,value) for key,value in request.GET.items() if not key.startswith('sf_') and key not in ('sq','page') and not key.endswith('_page')]
    from urllib.parse import urlencode
    return {'structure_current':current,'structure_filter_form':filters,'structure_preserved':preserved,
            'structure_clear_url':request.path+'?'+urlencode(preserved),
            'structure_list_payload':getattr(request,'_structure_list_payload',{}),
            'structure_custom_sections':[section for section in all_schemas(request).values() if section.custom and section.enabled and can_access(request.user,section)]}


def form_values_for_subject(section,subject,user):
    content=ContentType.objects.get_for_model(subject)
    record=section.records.filter(content_type=content,object_id=subject.pk).first()
    result={}
    for item in fields_for(section,user):
        if item.native_name:continue
        value=record.data.get(item.key,item.default_value) if record else item.default_value
        validator=typed_field(item)
        if value not in (None,''):
            try:value=validator.clean(value)
            except ValidationError:pass
        result['extra_'+item.key]=validator.prepare_value(value)
    return result
