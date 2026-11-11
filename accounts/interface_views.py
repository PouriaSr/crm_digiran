from uuid import uuid4
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.urls import reverse
from crm.pagination import paginate
from .models import InterfaceComponent, InterfaceChange, SectionSchema
from .permissions import require_permission, require_roles, ROLE_ADMIN, ROLE_SALES_MANAGER
from .interface import catalog, permitted, internal_url
from .interface_forms import InterfaceForm
from .builder_presentation import section_cards, editor_groups, section_preview


def snapshot(component):
    return {key:getattr(component,key) for key in ('key','kind','section','label','enabled','position','roles','permission','url','scope_path','body','custom','revision','behavior','scope_key')}


@login_required
@require_roles(ROLE_ADMIN, ROLE_SALES_MANAGER)
@require_permission('system.configure')
@require_GET
def settings(request):
    scope=request.GET.get('scope','')
    if scope and not SectionSchema.objects.filter(key=scope).exists():
        from django.http import Http404
        raise Http404
    overrides = {item.key:item for item in InterfaceComponent.objects.all()}
    rows = []
    for key, default in catalog().items():
        item = overrides.get(key)
        rows.append({**default, 'key':key, 'label':(item.label if item else default['label']),
                     'enabled':item.enabled if item else True, 'changed':bool(item), 'custom':False})
    rows += [snapshot(item) | {'changed':True} for item in overrides.values() if item.custom]
    if scope:
        from .structure_registry import component_scopes
        rows=[row for row in rows if scope in component_scopes(row['key'],row) or overrides.get(row['key']) and overrides[row['key']].scope_key==scope]
    titles={'tab':'تب','button':'دکمه','column':'ستون فهرست','field':'عنوان ورودی','link':'لینک','heading':'عنوان'}
    for row in rows:row['kind_title']=titles.get(row['kind'],row['kind'])
    sections = sorted({row['section'] for row in rows})
    query = request.GET.get('q','').strip()[:200]
    section, kind = request.GET.get('section',''), request.GET.get('kind','')
    if query:rows=[row for row in rows if query.casefold() in (row['label']+' '+row['key']+' '+row['section']).casefold()]
    if section:rows=[row for row in rows if row['section']==section]
    if kind:rows=[row for row in rows if row['kind']==kind]
    if request.GET.get('changed')=='1':rows=[row for row in rows if row['changed']]
    preferred=['مرکز مشتریان','راهبری سیستم','منابع انسانی','پیام‌رسانی','کالاها','فاکتورها','تبلیغات','کاربران و حساب','تماس‌ها','داشبورد']
    rows.sort(key=lambda row:(preferred.index(row['section']) if row['section'] in preferred else 99, {'tab':0,'button':1,'column':2,'field':3,'link':4}.get(row['kind'],5),row.get('position',100),row['key']))
    return render(request,'accounts/interface_settings.html',{'components':paginate(request,rows), 'sections':sections,
        'section_cards':section_cards(SectionSchema.objects.order_by('position','pk')) if not request.GET.get('q') and not scope else [],'scope':scope,
        'component_count':len(catalog()), 'changes':InterfaceChange.objects.select_related('actor')[:8], 'query':query})


@login_required
@require_roles(ROLE_ADMIN, ROLE_SALES_MANAGER)
@require_permission('system.configure')
@require_http_methods(['GET','POST'])
@transaction.atomic
def edit(request, key=None):
    definition = catalog().get(key) if key else None
    scope=request.GET.get('scope','')
    if request.method=='GET' and key and key.startswith('hub.tab.') and request.GET.get('details')!='1':
        target='invoices' if key.endswith('.invoice') else key.split('.')[-1]
        return redirect('accounts:structure_section',section_key=target)
    if scope and definition:
        from .structure_registry import component_scopes
        if scope not in component_scopes(key,definition):raise PermissionDenied('این جزء به بخش انتخاب‌شده مربوط نیست.')
    instance = InterfaceComponent.objects.select_for_update().filter(key=key).first() if key else None
    if key and not instance and not definition:
        from django.http import Http404
        raise Http404
    if not instance:
        instance=InterfaceComponent(key=key or 'custom.'+uuid4().hex, custom=not definition,
            **({name:definition[name] for name in ('kind','section','label','position')} if definition else {'kind':'tab','section':'سفارشی'}))
        instance.revision=0
    before = snapshot(instance) if instance.pk else {}
    form=InterfaceForm(request.POST or None, instance=instance, definition=definition)
    if request.method=='POST' and form.is_valid():
        if form.cleaned_data.get('revision') != before.get('revision',0):
            form.add_error(None,'این تنظیم هم‌زمان تغییر کرده است؛ صفحه را تازه کنید و دوباره بررسی کنید.')
        else:
            component=form.save(commit=False)
            if scope:component.scope_key=scope
            component.revision=before.get('revision',0)+1
            component.updated_by=request.user
            component.save()
            InterfaceChange.objects.create(key=component.key,action='update' if before else 'create',before=before,after=snapshot(component),actor=request.user)
            messages.success(request,'تنظیم ذخیره شد و در بارگذاری بعدی صفحات اعمال می‌شود.')
            return redirect('accounts:structure_section',section_key=scope) if scope else redirect('accounts:interface_settings')
    from .structure_registry import component_scopes
    candidates=component_scopes(key,definition) if definition else []
    preview_section=SectionSchema.objects.filter(key=scope).first() if scope else SectionSchema.objects.filter(key__in=candidates).first()
    preview=section_preview(preview_section) if preview_section else {'label':'بخش نمونه','fields':[],'columns':[],'stages':[],'transitions':[]}
    preview['component_kind']=definition['kind'] if definition else instance.kind
    return render(request,'accounts/interface_form.html',{'form':form,'component':instance,'definition':definition,'scope':scope,
        'builder_preview':preview,'editor_groups':editor_groups(form,'component')})


@login_required
@require_roles(ROLE_ADMIN, ROLE_SALES_MANAGER)
@require_permission('system.configure')
@require_POST
@transaction.atomic
def reset(request, key):
    item=InterfaceComponent.objects.select_for_update().filter(key=key).first()
    if item:
        if request.POST.get('revision') != str(item.revision):
            messages.error(request,'تنظیم تغییر کرده است؛ صفحه را تازه کنید.')
            return redirect('accounts:interface_edit',key=key)
        InterfaceChange.objects.create(key=key,action='delete' if item.custom else 'reset',before=snapshot(item),actor=request.user)
        item.delete()
    return redirect('accounts:interface_settings')


@login_required
@require_GET
def page(request, pk):
    item=get_object_or_404(InterfaceComponent,pk=pk,custom=True)
    if not permitted(request.user,item):raise PermissionDenied
    if item.url:return redirect(internal_url(item.url))
    return render(request,'accounts/interface_page.html',{'component':item})
