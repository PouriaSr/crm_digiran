from datetime import date,datetime
from decimal import Decimal
from django import forms
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q,Subquery,FloatField,F,OuterRef
from django.db.models.functions import Cast
from django.urls import reverse
from .models import SectionRecord
from .structure_registry import SECTIONS,LIST_BINDINGS,scope_for_request
from .structure_service import schema,typed_field,fields_for,native_visible,serialized,choice_pairs


def adapter(section,model):
    if model==SectionRecord:return ''
    native=SECTIONS.get(section.key)
    if not native:return None
    if model._meta.label==native['model']:return ''
    bound=LIST_BINDINGS.get(section.key)
    return bound[1] if bound and model._meta.label==bound[0] else None


def allowed_columns(section,user):
    fields={field.key:field for field in fields_for(section,user) if not field.native_name}
    sources={'native:'+path for path in SECTIONS.get(section.key,{}).get('fields',[])}
    from .permissions import has_permission
    blocked=set()
    if section.key in ('info','registration') and not has_permission(user,'customers.profile_full'):blocked|={'native:email','native:address'}
    if section.key=='products' and not has_permission(user,'products.edit'):blocked.add('native:cost_price')
    return [column for column in section.columns.all() if column.source not in blocked and column.enabled and (column.source in sources or column.source.startswith('extra:') and column.source[6:] in fields or column.source=='system:record')]


def filter_form(request,section):
    columns=allowed_columns(section,request.user)
    form=forms.Form(request.GET)
    fields={field.key:field for field in fields_for(section,request.user)}
    for column in columns:
        if not column.filterable or column.source=='system:record':continue
        if column.source.startswith('extra:'):
            field=typed_field(fields[column.source[6:]])
            field.required=False;field.disabled=False
            if fields[column.source[6:]].field_type=='boolean':field=forms.ChoiceField(choices=[('','همه'),('true','بله'),('false','خیر')],required=False)
        else:field=forms.CharField(required=False)
        field.label=column.label
        field.widget.attrs.pop('id',None)
        form.fields['sf_'+column.key]=field
    if any(column.searchable for column in columns):form.fields['sq']=forms.CharField(label='جستجوی فهرست',required=False)
    return form


def filter_records(request,section,records,custom=False):
    relation=adapter(section,records.model)
    if relation is None:return records
    form=filter_form(request,section)
    request._structure_filter_form=form
    if not form.is_valid():return records.none()
    data=form.cleaned_data
    definitions={field.key:field for field in fields_for(section,request.user)}
    columns=allowed_columns(section,request.user)
    prefix=relation+'__' if relation else ''
    native=SECTIONS.get(section.key)
    def extra_ids(source,value,search=False):
        field=definitions[source[6:]]
        values=SectionRecord.objects.filter(section=section)
        if native:values=values.filter(content_type=ContentType.objects.get_for_model(apps.get_model(native['model'])))
        lookup='data__'+field.key
        if field.field_type=='boolean':value=value=='true' if isinstance(value,str) else bool(value)
        if field.field_type in ('text','longtext','email','url') or search:lookup+='__icontains'
        if isinstance(value,(date,Decimal)):value=serialized(value)
        return values.filter(**{lookup:value}).values('pk' if custom else 'object_id')
    for column in columns:
        value=data.get('sf_'+column.key)
        if value in ('',None):continue
        if column.source.startswith('extra:'):records=records.filter(**{prefix+'pk__in':extra_ids(column.source,value)})
        elif column.source.startswith('native:'):
            path=column.source[7:]
            model=apps.get_model(native['model'])
            for part in path.split('__'):
                field=model._meta.get_field(part)
                if field.is_relation:model=field.related_model
            try:
                converted=field.clean(value,None) if not field.is_relation else int(value)
            except Exception:
                form.add_error('sf_'+column.key,'مقدار معتبر وارد کنید.');return records.none()
            lookup=prefix+path+('__icontains' if field.get_internal_type() in ('CharField','TextField') else '')
            records=records.filter(**{lookup:converted})
    query=data.get('sq','').strip()
    if query:
        condition=Q(pk__in=[])
        for column in columns:
            if not column.searchable:continue
            if column.source.startswith('extra:'):condition|=Q(**{prefix+'pk__in':extra_ids(column.source,query,True)})
            elif column.source.startswith('native:'):condition|=Q(**{prefix+column.source[7:]+'__icontains':query})
        records=records.filter(condition)
    source=section.sort_source
    valid={'extra:'+key for key in definitions}|{'native:'+key for key in SECTIONS.get(section.key,{}).get('fields',[])}
    if source and source in valid:
        if source.startswith('native:'):records=records.order_by(('-' if section.descending else '')+prefix+source[7:],'-pk')
        else:
            extra=SectionRecord.objects.filter(section=section,object_id=OuterRef(prefix+'pk')).values('data__'+source[6:])[:1]
            expression=Subquery(extra)
            if custom:expression=F('data__'+source[6:])
            if definitions[source[6:]].field_type in ('integer','decimal'):expression=Cast(expression,FloatField())
            records=records.annotate(_structure_sort=expression).order_by(('-' if section.descending else '')+'_structure_sort','-pk')
    return records


def native_value(subject,path):
    parts=path.split('__');obj=subject
    for part in parts[:-1]:obj=getattr(obj,part,None)
    if obj is None:return ''
    name=parts[-1]
    if hasattr(obj,'get_'+name+'_display'):return getattr(obj,'get_'+name+'_display')()
    value=getattr(obj,name,'')
    if value is None:return ''
    if isinstance(value,(str,int,float,bool)):return value
    if isinstance(value,(datetime,date)):return value.isoformat()
    return str(value)


def attach_rows(request,section,page):
    columns=allowed_columns(section,request.user)
    hidden=[column.component_key for column in section.columns.all() if not column.enabled and column.component_key]
    if not columns and not hidden:return
    relation=adapter(section,page.object_list.model) if hasattr(page.object_list,'model') else None
    if relation is None:return
    row_kind=page.object_list.model._meta.model_name if hasattr(page.object_list,'model') else ''
    records=list(page)
    if section.custom:
        request._structure_list_payload={'section':section.key,'row_kind':'sectionrecord','hidden':hidden,'rows':{str(row.pk):{'values':{column.key:row.data.get(column.source[6:],'') for column in columns if column.source.startswith('extra:')},'url':reverse('accounts:structure_record',args=[section.key,row.pk])} for row in records},'columns':column_payload(columns)}
        page.object_list=records
        return
    subjects={}
    for row in records:
        subject=row
        try:
            for part in relation.split('__') if relation else []:subject=getattr(subject,part)
        except Exception:subject=None
        if subject is not None and native_visible(request.user,section,subject):subjects[row.pk]=subject
    content=ContentType.objects.get_for_model(apps.get_model(SECTIONS[section.key]['model']))
    extra={record.object_id:record for record in SectionRecord.objects.filter(section=section,content_type=content,object_id__in=[subject.pk for subject in subjects.values()])}
    result={}
    for pk,subject in subjects.items():
        record=extra.get(subject.pk)
        values={}
        for column in columns:
            if column.source.startswith('extra:'):
                values[column.key]=record.data.get(column.source[6:],'') if record else ''
                definition=next((field for field in section.fields.all() if field.key==column.source[6:]),None)
                if definition and definition.field_type=='choice':values[column.key]=dict(choice_pairs(definition)).get(str(values[column.key]),values[column.key])
            elif column.source.startswith('native:'):values[column.key]=native_value(subject,column.source[7:])
        result[str(pk)]={'values':values,'url':reverse('accounts:structure_native_record',args=[section.key,subject.pk])}
    request._structure_list_payload={'section':section.key,'hidden':hidden, 'row_kind':row_kind, 'rows':result,'columns':column_payload(columns)}
    page.object_list=records


def column_payload(columns):
    return [{'key':c.key,'component':c.component_key,'label':c.label,'position':c.position,'width':c.width,'align':c.align,'display':c.display,'wrap':c.wrap,'source':c.source,'choices':dict(choice_pairs(next((field for field in c.section.fields.all() if c.source=='extra:'+field.key),None))) if any(c.source=='extra:'+field.key and field.field_type=='choice' for field in c.section.fields.all()) else {}} for c in columns]
