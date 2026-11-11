import json
from uuid import uuid4
from django.apps import apps
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.forms.models import model_to_dict
from django.shortcuts import get_object_or_404,redirect,render
from django.urls import reverse
from django.views.decorators.http import require_GET,require_POST,require_http_methods
from django.contrib.auth.decorators import login_required
from crm.pagination import paginate
from .models import SectionSchema,SectionField,SectionColumn,SectionStage,SectionTransition,SectionRecord,SectionRecordEvent,InterfaceChange
from .permissions import require_roles,require_permission,ROLE_ADMIN,ROLE_SALES_MANAGER,get_user_role,has_permission
from .structure_registry import SECTIONS,component_scopes
from .structure_service import schema,RecordForm,require_access,native_subject,native_visible,record_access,save_record,transition_record,typed_field,serialized
from .structure_forms import SectionForm,FieldForm,ColumnForm,StageForm,TransitionForm
from .interface import catalog
from .builder_presentation import section_preview, editor_groups, element_meta


def audit_snapshot(item):
    return json.loads(json.dumps(model_to_dict(item),default=str))


def scoped_components(section, preview=None):
    from .models import InterfaceComponent
    overrides={item.key:item for item in InterfaceComponent.objects.all()}
    rows=[{'key':key,**definition,'label':overrides[key].label if key in overrides else definition['label']}
          for key,definition in catalog().items() if section.key in component_scopes(key,definition)]
    rows += [{'key':item.key,'label':item.label,'kind':item.kind,'custom':True}
             for item in overrides.values() if item.custom and item.scope_key==section.key]
    from .builder_usage import annotate_components
    return annotate_components(section,rows,preview or section_preview(section),overrides)


@login_required
@require_roles(ROLE_ADMIN,ROLE_SALES_MANAGER)
@require_permission('system.configure')
@require_http_methods(['GET','POST'])
def section_edit(request,section_key=None):
    section=get_object_or_404(SectionSchema,key=section_key) if section_key else SectionSchema(key='custom-'+uuid4().hex[:12],custom=True)
    before=audit_snapshot(section) if section.pk else {}
    form=SectionForm(request.POST or None,instance=section)
    if not section.pk:form.initial.update({'revision':0,'roles':[ROLE_ADMIN,ROLE_SALES_MANAGER]})
    if request.method=='POST' and not has_permission(request.user,'system.schema'):raise PermissionDenied
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            if section.pk:
                current=SectionSchema.objects.select_for_update().get(pk=section.pk)
                if form.cleaned_data.get('revision')!=current.revision:
                    form.add_error(None,'این بخش هم‌زمان ویرایش شده است؛ صفحه را تازه کنید.')
            if not form.errors:
                item=form.save(commit=False);item.revision=before.get('revision',0)+1;item.save()
                if item.key in ('info','reception','case','registration','hiring','invoices'):
                    tab='invoice' if item.key=='invoices' else item.key
                    from .models import InterfaceComponent
                    existing=InterfaceComponent.objects.filter(key='hub.tab.'+tab).first()
                    values={'label':item.label,'enabled':item.enabled,'roles':item.roles,'permission':item.permission,'position':item.position,'revision':existing.revision+1 if existing else 1,'updated_by':request.user}
                    InterfaceComponent.objects.update_or_create(key='hub.tab.'+tab,defaults={**values,'kind':'tab','section':'مرکز مشتریان'})
                InterfaceChange.objects.create(key='section:'+item.key,action='update' if before else 'create',before=before,after=audit_snapshot(item),actor=request.user)
                return redirect(reverse('accounts:structure_section',args=[item.key])+'?saved=1#section-settings')
    preview=section_preview(section)
    related=scoped_components(section,preview) if section.pk else []
    related=[item for item in related if not item['key'].startswith('hub.tab.')]
    from .builder_usage import native_inventory
    native_fields=native_inventory(section,preview) if section.pk else []
    definitions={item.key:item for item in section.fields.all()} if section.pk else {}
    for field in preview['fields']:
        key=next((key for key,item in definitions.items() if (item.native_name or key)==field['key']),None)
        if key:definitions[key].builder_usage=field['usage']
    columns=list(section.columns.all()) if section.pk else []
    for item,metadata in zip(columns,preview['columns']):
        item.builder_usage=metadata['usage'];item.filter_usage=metadata['filter_usage'];item.search_usage=metadata['search_usage']
    stages=list(section.stages.all()) if section.pk else []
    transitions=list(section.transitions.select_related('source','target')) if section.pk else []
    for items,key in ((stages,'stages'),(transitions,'transitions')):
        for item,metadata in zip(items,preview[key]):item.builder_usage=metadata['usage']
    return render(request,'accounts/structure_section.html',{'section':section,'form':form,'related_components':related,'native_fields':native_fields,'native_primary_count':sum(item['primary'] for item in native_fields),
        'builder_preview':preview,'editor_groups':editor_groups(form,'section'),
        'native_definition':SECTIONS.get(section.key),'fields_list':list(definitions.values()),
        'columns_list':columns,'stages_list':stages,'transitions_list':transitions})


EDITORS={'field':(SectionField,FieldForm),'column':(SectionColumn,ColumnForm),'stage':(SectionStage,StageForm),'transition':(SectionTransition,TransitionForm)}


@login_required
@require_roles(ROLE_ADMIN,ROLE_SALES_MANAGER)
@require_permission('system.configure')
@require_http_methods(['GET','POST'])
@transaction.atomic
def element_edit(request,section_key,kind,pk=None):
    if kind not in EDITORS:
        from django.http import Http404
        raise Http404
    if not has_permission(request.user,'system.workflow' if kind in ('stage','transition') else 'system.schema'):raise PermissionDenied
    section=get_object_or_404(SectionSchema,key=section_key)
    model,form_class=EDITORS[kind]
    item=get_object_or_404(model.objects.select_for_update(),pk=pk,section=section) if pk else model(section=section)
    if not pk and kind in ('field','column'):item.key=kind+'_'+uuid4().hex[:12]
    before=audit_snapshot(item) if item.pk else {}
    if kind=='column' and not pk and request.GET.get('component'):
        component=request.GET['component'];definition=catalog().get(component)
        if not definition or definition['kind']!='column' or section.key not in component_scopes(component,definition):raise PermissionDenied
        item.component_key=component;item.label=definition['label']
    form=form_class(request.POST or None,instance=item,section=section,**({'initial':{'native_name':request.GET.get('native','')}} if kind=='field' and not pk and request.GET.get('native') else {}))
    if not item.pk:form.initial['revision']=0
    if request.method=='POST' and form.is_valid():
        if form.cleaned_data.get('revision')!=before.get('revision',0):form.add_error(None,'این جزء هم‌زمان تغییر کرده است؛ صفحه را تازه کنید.')
        converted=[]
        if kind=='field' and item.pk and not item.native_name and not form.errors and any(before.get(name)!=audit_snapshot(item).get(name) for name in ('field_type','choices','minimum','maximum','max_length')):
            # Validate type/options changes against all stored values before applying anything.
            errors=[]
            for record in section.records.all().iterator():
                value=record.data.get(item.key)
                if value in (None,''):continue
                validator=typed_field(item);validator.required=False
                if item.field_type=='choice':
                    from .behavior_service import effective_options
                    validator.choices=[('', 'انتخاب کنید…')]+[(option['key'],option['label']) for option in effective_options(section,'extra_'+item.key,validator,True)]
                try:new=serialized(validator.clean(value))
                except ValidationError:
                    errors.append(str(record.pk));continue
                if new!=value:converted.append((record,new))
            if errors:form.add_error('field_type','این تغییر با داده قبلی سازگار نیست؛ رکوردها: '+', '.join(errors[:12]))
        if not form.errors:
            saved=form.save(commit=False);saved.revision=before.get('revision',0)+1;saved.save()
            for record,value in converted:
                old_data=record.data.copy();record.data={**record.data,saved.key:value};record.revision+=1;record.save(update_fields=['data','revision','updated_at'])
                SectionRecordEvent.objects.create(record=record,actor=request.user,before={'data':old_data},after={'data':record.data},note='تبدیل نوع فیلد با ویرایش ساختار')
            InterfaceChange.objects.create(key=f'section:{section.key}:{kind}:{saved.pk}',action='update' if before else 'create',before=before,after=audit_snapshot(saved),actor=request.user)
            panel=element_meta(kind)[2]
            return redirect(reverse('accounts:structure_section',args=[section.key])+'?saved=1#section-'+panel)
    title,hint,panel=element_meta(kind)
    return render(request,'accounts/structure_element.html',{'section':section,'element':item,'form':form,'kind':kind,
        'builder_preview':section_preview(section),'editor_groups':editor_groups(form,kind),
        'editor_title':title,'editor_hint':hint,'editor_panel':panel,
        'editor_key':(item.native_name or item.key) if kind=='field' else item.key if kind=='column' else str(item.pk) if item.pk else 'draft'})


@login_required
@require_roles(ROLE_ADMIN,ROLE_SALES_MANAGER)
@require_permission('system.configure')
@require_POST
@transaction.atomic
def element_archive(request,section_key,kind,pk):
    if kind not in EDITORS or not has_permission(request.user,'system.workflow' if kind in ('stage','transition') else 'system.schema'):raise PermissionDenied
    section=get_object_or_404(SectionSchema,key=section_key)
    item=get_object_or_404(EDITORS[kind][0].objects.select_for_update(),pk=pk,section=section)
    if str(item.revision)!=request.POST.get('revision'):
        messages.error(request,'این جزء تغییر کرده است؛ صفحه را تازه کنید.')
        return redirect('accounts:structure_element_edit',section_key=section.key,kind=kind,pk=pk)
    if kind=='field':
        blocked=[stage.label for stage in section.stages.filter(enabled=True) if item.key in stage.required_fields]
        if blocked:
            messages.error(request,'ابتدا الزام این فیلد را از مراحل مرتبط حذف کنید: '+', '.join(blocked))
            return redirect('accounts:structure_element_edit',section_key=section.key,kind=kind,pk=pk)
    before=audit_snapshot(item);item.enabled=False;item.revision+=1;item.save()
    InterfaceChange.objects.create(key=f'section:{section.key}:{kind}:{item.pk}',action='archive',before=before,after=audit_snapshot(item),actor=request.user)
    return redirect('accounts:structure_section',section_key=section.key)


def records_queryset(section,user,archived=False):
    records=section.records.filter(archived=archived).select_related('stage','owner')
    from customers.access import is_card_manager
    if not is_card_manager(user):records=records.filter(owner=user)
    return records


@login_required
@require_GET
def data_list(request,section_key):
    section=get_object_or_404(SectionSchema,key=section_key)
    require_access(request.user,section)
    request._structure_scope=section.key
    if section.custom:
        records=records_queryset(section,request.user,request.GET.get('archived')=='1')
    else:
        definition=SECTIONS[section.key]
        model=apps.get_model(definition['model'])
        records=model._default_manager.all().order_by('-pk')
        from customers.access import is_card_manager
        if section.key=='info' and not has_permission(request.user,'customers.candidate_view'):records=records.filter(is_interviewer=False)
        if section.key=='registration':records=records.filter(is_interviewer=False)
        if section.key=='case':records=records.filter(customer__is_interviewer=False)
        if not is_card_manager(request.user):
            if section.key=='info':
                from django.db.models import Q
                records=records.filter(Q(is_interviewer=False)|Q(assigned_to=request.user)|Q(created_by=request.user)) if has_permission(request.user,'customers.candidate_view') else records.filter(is_interviewer=False)
            elif section.key=='registration':records=records.filter(assigned_to=request.user)
            elif section.key=='case':records=records.filter(customer__assigned_to=request.user)
            elif section.key=='hiring':records=records.filter(reception__customer__assigned_to=request.user)
            elif section.key=='tasks':
                from hr.task_access import visible_tasks
                records=visible_tasks(request.user)
            elif section.key in ('invoices','ads'):records=records.filter(created_by=request.user)
            elif section.key=='calls':records=records.filter(called_by=request.user)
    page=paginate(request,records)
    from django.contrib.contenttypes.models import ContentType
    items=list(page)
    existing={row.object_id:row for row in section.records.filter(object_id__in=[item.pk for item in items])} if not section.custom else {}
    page.object_list=[{'pk':item.pk,'archived':getattr(item,'archived',False),'revision':getattr(item,'revision',1),'kind':item._meta.model_name,'title':item.title if section.custom else str(item),'stage':item.stage if section.custom else getattr(existing.get(item.pk),'stage',None),
        'structure_url':reverse('accounts:structure_record' if section.custom else 'accounts:structure_native_record',args=[section.key,item.pk])} for item in items]
    return render(request,'accounts/structure_data_list.html',{'section':section,'records':page})


@login_required
@require_http_methods(['GET','POST'])
@transaction.atomic
def data_edit(request,section_key,pk=None,native_pk=None):
    section=get_object_or_404(SectionSchema,key=section_key)
    require_access(request.user,section,request.method=='POST')
    subject=native_subject(section,native_pk,request.user,request.method=='POST') if native_pk else None
    record=get_object_or_404(SectionRecord.objects.select_for_update().select_related('section','stage'),pk=pk,section=section,archived=False) if pk else None
    if subject:
        from django.contrib.contenttypes.models import ContentType
        record=section.records.filter(content_type=ContentType.objects.get_for_model(subject),object_id=subject.pk).first()
    if record:record_access(request.user,record,request.method=='POST')
    if not subject and not record and not section.custom:
        from django.http import Http404
        raise Http404
    form=RecordForm(request.POST or None,section=section,user=request.user,record=record)
    if request.method=='POST' and form.is_valid():
        if request.POST.get('transition'):
            if not record:form.add_error(None,'ابتدا اطلاعات رکورد را ذخیره کنید.')
            else:
                raw=request.POST['transition']
                if not raw.isascii() or not raw.isdigit() or len(raw)>16:raise PermissionDenied('اقدام معتبر نیست.')
                step=get_object_or_404(SectionTransition,pk=raw,section=section)
                try:
                    # Changes and transition commit together; failed transition rolls back values.
                    with transaction.atomic():
                        updated=save_record(section,form.values(),request.user,record=record,revision=form.cleaned_data.get('revision'),subject=subject)
                        record=transition_record(updated,step,request.user,updated.revision,request.POST.get('note',''))
                    return redirect('accounts:structure_record',section_key=section.key,pk=record.pk)
                except ValidationError as error:form.add_error(None,error)
        else:
            try:
                record=save_record(section,form.values(),request.user,record=record,title=form.cleaned_data.get('title',''),revision=form.cleaned_data.get('revision') if record else None,subject=subject)
                return redirect('accounts:structure_record',section_key=section.key,pk=record.pk)
            except ValidationError as error:form.add_error(None,error)
    steps=section.transitions.filter(source_id=record.stage_id,enabled=True,target__enabled=True).select_related('target') if record and record.stage_id else []
    steps=[step for step in steps if not step.roles or get_user_role(request.user) in step.roles]
    try:
        require_access(request.user,section,True)
        if record:record_access(request.user,record,True)
        elif subject and not native_visible(request.user,section,subject,True):raise PermissionDenied
        editable=True
    except PermissionDenied:
        editable=False;steps=[]
        for field in form.fields.values():field.disabled=True
    return render(request,'accounts/structure_record.html',{'section':section,'record':record,'subject':subject,'form':form,'steps':steps,'editable':editable,
        'events':record.events.select_related('actor')[:20] if record else []})


@login_required
@require_roles(ROLE_ADMIN,ROLE_SALES_MANAGER)
@require_permission('system.configure')
@require_POST
@transaction.atomic
def apply_existing(request,section_key):
    if not has_permission(request.user,'system.workflow'):raise PermissionDenied
    section=get_object_or_404(SectionSchema,key=section_key)
    require_access(request.user,section,True)
    if section.custom:return redirect('accounts:structure_section',section_key=section.key)
    model=apps.get_model(SECTIONS[section.key]['model'])
    total,skipped=0,0
    from .structure_service import fields_for
    definitions=[field for field in fields_for(section,request.user) if not field.native_name]
    for subject in model._default_manager.all().iterator(chunk_size=200):
        if not native_visible(request.user,section,subject,True):continue
        try:
            with transaction.atomic():
                from django.contrib.contenttypes.models import ContentType
                current=section.records.filter(content_type=ContentType.objects.get_for_model(subject),object_id=subject.pk).first()
                values={field.key:serialized(typed_field(field).clean(field.default_value or None)) for field in definitions if not current or field.key not in current.data}
                save_record(section,values,request.user,record=current,subject=subject)
                total+=1
        except ValidationError:skipped+=1
    messages.success(request,f'{total} رکورد همگام شد؛ {skipped} رکورد به تکمیل اطلاعات الزامی نیاز دارد. داده قبلی پاک نشد.')
    return redirect('accounts:structure_section',section_key=section.key)


@login_required
@require_POST
@transaction.atomic
def record_archive(request,section_key,pk):
    section=get_object_or_404(SectionSchema,key=section_key,custom=True)
    record=get_object_or_404(SectionRecord.objects.select_for_update().select_related('section'),pk=pk,section=section)
    record_access(request.user,record,True)
    if request.POST.get('revision')!=str(record.revision):
        messages.error(request,'رکورد هم‌زمان تغییر کرده است؛ صفحه را تازه کنید.')
        return redirect('accounts:structure_data',section_key=section.key)
    before=record.archived
    record.archived=request.POST.get('restore')!='1';record.revision+=1;record.save(update_fields=['archived','revision','updated_at'])
    SectionRecordEvent.objects.create(record=record,actor=request.user,before={'archived':before},after={'archived':record.archived},note='بایگانی رکورد' if record.archived else 'بازگردانی رکورد')
    from hr.models import Task
    if record.archived:
        for task in Task.objects.filter(source_type='structure',source_id=record.pk).exclude(status__in=['done','cancelled']):task.status='cancelled';task.save()
    else:
        from .structure_service import sync_stage_task
        sync_stage_task(record,request.user)
    return redirect('accounts:structure_data',section_key=section.key)
