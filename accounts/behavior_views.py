from uuid import uuid4
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404,render,redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods,require_POST
from .permissions import require_roles,require_permission,ROLE_ADMIN,ROLE_SALES_MANAGER
from .models import SectionSchema,SectionBehavior,SectionOption,InterfaceChange
from .behavior_forms import BehaviorForm,OptionForm
from .behavior_service import prototypes,base_options,effective_options
from .builder_presentation import section_preview
from .structure_views import audit_snapshot


def catalog_payload(section):
    result={}
    for name,field in prototypes(section).items():
        result[name]={'label':str(field.label or name),'options':([{'key':'true','label':'انتخاب شده'},{'key':'false','label':'انتخاب نشده'}] if isinstance(field,forms.BooleanField) else effective_options(section,name,field)),'condition_options':effective_options(section,name,field,True),'multiple':isinstance(field,forms.MultipleChoiceField),'reference':isinstance(field,forms.ModelChoiceField),'reference_url':reverse('accounts:behavior_reference_options',args=[section.key])+'?field='+name}
    return result


def inspector_url(section,name):return reverse('accounts:behavior_inspector',args=[section.key,name])


@login_required
@require_roles(ROLE_ADMIN,ROLE_SALES_MANAGER)
@require_permission('system.configure')
@require_http_methods(['GET'])
def inspector(request,section_key,field_name):
    section=get_object_or_404(SectionSchema,key=section_key)
    field=prototypes(section).get(field_name)
    if field is None:raise PermissionDenied('این ورودی به بخش انتخاب‌شده مربوط نیست.')
    reference_url=''
    if isinstance(field,forms.ModelChoiceField):
        from .structure_registry import SECTIONS
        from .interface import internal_url
        definition=next((entry for entry in SECTIONS.values() if entry['model']==field.queryset.model._meta.label),None)
        if definition:reference_url=internal_url(definition['path']+('?tab='+definition['tab'] if definition.get('tab') else ''))
    rules=section.behaviors.filter(source=field_name)
    native_rule=section.fields.filter(native_name=field_name).first() if not field_name.startswith('extra_') else section.fields.filter(key=field_name[6:]).first()
    edit_url=reverse('accounts:structure_element_edit',args=[section.key,'field',native_rule.pk]) if native_rule else reverse('accounts:structure_element_create',args=[section.key,'field'])+'?native='+field_name
    preview=section_preview(section)
    for metadata in preview['fields']:
        if (metadata['key'] if metadata['native'] else 'extra_'+metadata['key'])==field_name:metadata['highlight']=True;metadata['context_selected']=True
    return render(request,'accounts/behavior_inspector.html',{'section':section,'field_name':field_name,'field_label':field.label,'options':effective_options(section,field_name,field,True),
        'reference_url':reference_url,'reference':isinstance(field,forms.ModelChoiceField),'choice_field':isinstance(field,forms.ChoiceField),'rules':rules,'edit_url':edit_url,'builder_preview':preview})


@login_required
@require_roles(ROLE_ADMIN,ROLE_SALES_MANAGER)
@require_permission('system.configure')
@require_permission('system.schema')
@require_http_methods(['GET','POST'])
@transaction.atomic
def option_edit(request,section_key,field_name,pk=None):
    section=get_object_or_404(SectionSchema,key=section_key)
    prototype=prototypes(section).get(field_name)
    if not isinstance(prototype,forms.ChoiceField) or isinstance(prototype,forms.ModelChoiceField):raise PermissionDenied('گزینه‌های این ورودی از فهرست مرجع مدیریت می‌شوند.')
    key=request.GET.get('key','')
    item=get_object_or_404(SectionOption.objects.select_for_update(),pk=pk,section=section,field_name=field_name) if pk else section.options.select_for_update().filter(field_name=field_name,key=key).first() if key else None
    default=next((option for option in base_options(prototype) if option['key']==key),None)
    if key and not item and not default:raise PermissionDenied('گزینه اصلی وجود ندارد.')
    if item is None:
        item=SectionOption(section=section,field_name=field_name,key=key or 'option_'+uuid4().hex[:10],**({name:default[name] for name in ('label','base_value','position')} if default else {}))
    before=audit_snapshot(item) if item.pk else {}
    form=OptionForm(request.POST or None,instance=item,section=section,field_name=field_name)
    if key:form.fields['key'].disabled=True
    if not item.pk:form.initial['revision']=0
    if request.method=='POST' and form.is_valid():
        if form.cleaned_data.get('revision')!=before.get('revision',0):form.add_error(None,'این گزینه هم‌زمان تغییر کرده است؛ صفحه را تازه کنید.')
        elif section.options.filter(field_name=field_name,key=form.cleaned_data['key']).exclude(pk=item.pk).exists():form.add_error('key','این شناسه از قبل برای این ورودی وجود دارد.')
        else:
            saved=form.save(commit=False);saved.revision=before.get('revision',0)+1;saved.save()
            InterfaceChange.objects.create(key=f'option:{section.key}:{field_name}:{saved.key}',action='update' if before else 'create',before=before,after=audit_snapshot(saved),actor=request.user)
            return redirect(inspector_url(section,field_name)+'?saved=1')
    return render(request,'accounts/behavior_editor.html',{'section':section,'form':form,'item':item,'editor_type':'option','field_name':field_name,'field_label':prototype.label,'behavior_catalog':catalog_payload(section),'builder_preview':{**section_preview(section),'editing_field_name':field_name}})


@login_required
@require_roles(ROLE_ADMIN,ROLE_SALES_MANAGER)
@require_permission('system.configure')
@require_permission('system.workflow')
@require_http_methods(['GET','POST'])
@transaction.atomic
def rule_edit(request,section_key,pk=None):
    section=get_object_or_404(SectionSchema,key=section_key)
    item=get_object_or_404(SectionBehavior.objects.select_for_update(),pk=pk,section=section) if pk else SectionBehavior(section=section)
    before=audit_snapshot(item) if item.pk else {}
    form=BehaviorForm(request.POST or None,instance=item,section=section,actor=request.user,**({'initial':{'source':request.GET.get('source',''),'value':request.GET.get('value','')}} if not pk else {}))
    if not item.pk:form.initial['revision']=0
    if request.method=='POST' and form.is_valid():
        if form.cleaned_data.get('revision')!=before.get('revision',0):form.add_error(None,'این قاعده هم‌زمان تغییر کرده است؛ صفحه را تازه کنید.')
        else:
            saved=form.save(commit=False);saved.revision=before.get('revision',0)+1;saved.save()
            InterfaceChange.objects.create(key=f'behavior:{section.key}:{saved.pk}',action='update' if before else 'create',before=before,after=audit_snapshot(saved),actor=request.user)
            return redirect(inspector_url(section,saved.source)+'?saved=1')
    return render(request,'accounts/behavior_editor.html',{'section':section,'form':form,'item':item,'editor_type':'rule','field_name':item.source or request.GET.get('source',''),'behavior_catalog':catalog_payload(section),'builder_preview':section_preview(section)})


@login_required
@require_roles(ROLE_ADMIN,ROLE_SALES_MANAGER)
@require_permission('system.configure')
@require_POST
@transaction.atomic
def archive(request,section_key,kind,pk):
    from .permissions import has_permission
    permission='system.schema' if kind=='option' else 'system.workflow'
    if kind not in ('option','rule') or not has_permission(request.user,permission):raise PermissionDenied
    section=get_object_or_404(SectionSchema,key=section_key)
    item=get_object_or_404((SectionOption if kind=='option' else SectionBehavior).objects.select_for_update(),pk=pk,section=section)
    if str(item.revision)!=request.POST.get('revision'):raise PermissionDenied('این مورد تغییر کرده است؛ صفحه را تازه کنید.')
    before=audit_snapshot(item);item.enabled=False;item.revision+=1;item.save()
    InterfaceChange.objects.create(key=f'{kind}:{section.key}:{item.pk}',action='archive',before=before,after=audit_snapshot(item),actor=request.user)
    return redirect(inspector_url(section,item.field_name if kind=='option' else item.source))


@login_required
@require_roles(ROLE_ADMIN,ROLE_SALES_MANAGER)
@require_permission('system.configure')
@require_http_methods(['GET'])
def reference_options(request,section_key):
    from django.http import JsonResponse
    from .structure_service import require_access
    from django.db.models import Q,CharField
    section=get_object_or_404(SectionSchema,key=section_key)
    require_access(request.user,section)
    field=prototypes(section).get(request.GET.get('field',''))
    if not isinstance(field,forms.ModelChoiceField):raise PermissionDenied
    rows=field.queryset.all()
    query=request.GET.get('q','').strip()[:100]
    if query:
        condition=Q(pk__in=[])
        for native in rows.model._meta.fields:
            if isinstance(native,CharField) and native.name in ('name','label','title','username','first_name','last_name','mobile','phone_number'):condition|=Q(**{native.name+'__icontains':query})
        rows=rows.filter(condition)
    return JsonResponse({'options':[{'key':str(item.pk),'label':str(item)} for item in rows[:200]]})
