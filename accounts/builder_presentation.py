"""Presentation metadata for the section editor. Never reads business records."""
from django import forms
from django.urls import reverse
from django.utils.module_loading import import_string
from .interface import internal_url
from .structure_registry import SECTIONS
from .structure_service import choice_pairs

GROUPS = {
    'section': [
        ('نام و نمایش', 'عنوانی که کاربران در سیستم می‌بینند.', 'label,enabled,position', False),
        ('نمایش فهرست', 'تعداد ردیف‌ها و ترتیب اولیه فهرست.', 'page_size,sort_source,descending', False),
        ('دسترسی و فرآیند پیشرفته', '', 'roles,permission,gate_save,replace_form_logic', True),
    ],
    'field': [
        ('مشخصات ورودی', 'عنوان و نوع اطلاعاتی که کاربر وارد می‌کند.', 'label,field_type,required,enabled', False),
        ('ظاهر و راهنما', '', 'placeholder,help_text,default_value,options', False),
        ('قواعد و دسترسی پیشرفته', '', 'minimum,maximum,max_length,readonly,position,roles,native_name', True),
    ],
    'column': [
        ('محتوای ستون', 'داده‌ای که باید در این ستون نمایش داده شود.', 'label,source,component_key,enabled', False),
        ('نمایش و جستجو', '', 'display,align,filterable,searchable', False),
        ('اندازه و ترتیب پیشرفته', '', 'width,position,wrap', True),
    ],
    'stage': [
        ('مشخصات مرحله', 'جایگاه این مرحله در مسیر انجام کار.', 'label,status,initial,enabled', False),
        ('مسئول و وظیفه', '', 'create_task,assignee_role,assignee', False),
        ('قواعد مرحله', '', 'required_fields,position', True),
    ],
    'transition': [
        ('مسیر اقدام', 'با این اقدام، کار از کدام مرحله به کجا می‌رود؟', 'label,source,target,enabled', False),
        ('توضیح و دسترسی', '', 'require_note,roles', True),
    ],
    'component': [
        ('عنوان و نمایش', '', 'label,kind,enabled,appearance', False),
        ('عملکرد و راهنما', '', 'action_kind,destination,url,body,confirmation,tooltip,popup_text,popup_target', False),
        ('دسترسی و جایگاه پیشرفته', '', 'roles,permission,position,scope_path', True),
    ],
}


def editor_groups(form, kind):
    result = []
    for title, hint, names, advanced in GROUPS[kind]:
        fields = [form[name] for name in names.split(',') if name in form.fields and not form[name].is_hidden]
        for bound in fields:
            if isinstance(bound.field.widget, forms.Textarea):
                bound.field.widget.attrs['rows'] = 3 if bound.name != 'options' else 4
        if fields:
            result.append({'title': title, 'hint': hint, 'fields': fields, 'advanced': advanced,
                           'open': any(field.errors for field in fields)})
    return result


def field_type(field):
    if isinstance(field, forms.BooleanField): return 'boolean'
    if isinstance(field, forms.DecimalField): return 'decimal'
    if isinstance(field, forms.IntegerField): return 'integer'
    if isinstance(field, forms.DateField): return 'date'
    if isinstance(field, (forms.ChoiceField,forms.ModelChoiceField)): return 'choice'
    if isinstance(field, forms.EmailField): return 'email'
    if isinstance(field, forms.URLField): return 'url'
    if isinstance(field.widget, forms.Textarea): return 'longtext'
    return 'text'


def section_preview(section, focus_field=None, form_path=None):
    """Only field definitions and synthetic examples; no customer/task values."""
    fields = {}
    definition = SECTIONS.get(section.key, {})
    paths = definition.get('forms', [])
    # Secondary-form controls must be previewed in their actual form, not the contact form.
    active_path=next((path for path in reversed(paths) if focus_field in import_string(path).base_fields),paths[-1] if paths else None)
    if form_path in paths:active_path=form_path
    active_paths=[active_path] if active_path else []
    for path in active_paths:
        for index, (name, field) in enumerate(import_string(path).base_fields.items()):
            if name.startswith('password') or isinstance(field.widget, forms.HiddenInput): continue
            options = []
            if isinstance(field, forms.ChoiceField) and not isinstance(field, forms.ModelChoiceField):
                options = [{'value': str(v), 'label': str(l)} for v, l in field.choices
                           if v and not isinstance(l, (tuple, list))][:30]
            from .structure_forms_runtime import PROTECTED
            model=getattr(getattr(import_string(path),'_meta',None),'model',None)
            try:native=model._meta.get_field(name) if model else None
            except Exception:native=None
            locked=name in PROTECTED or bool(native and not native.null and not native.blank and not native.has_default())
            fields[name] = {'visibility_locked':locked,'key': name, 'label': str(field.label or name), 'field_type': field_type(field),
                            'multiple':isinstance(field,forms.MultipleChoiceField),'required': field.required, 'enabled': True, 'readonly': False,
                            'position': index * 10, 'placeholder': str(field.widget.attrs.get('placeholder', '')),
                            'help_text': '', 'default_value': '', 'choices': options, 'native': True, 'in_primary': True}
    primary_fields=list(fields)
    if section.key == 'info':
        for index, name in enumerate(('name','mobile','is_interviewer','call_type','purpose','call_status')):
            if name in fields: fields[name]['position'] = index * 10
    if section.pk:
        for item in section.fields.all():
            key = item.native_name or item.key
            prior = fields.get(key, {})
            in_primary = not item.native_name or key in primary_fields
            enabled,required = item.enabled,item.required
            if item.native_name and in_primary:
                from .structure_forms_runtime import PROTECTED
                model=getattr(getattr(import_string(active_path),'_meta',None),'model',None)
                try:native=model._meta.get_field(key) if model else None
                except Exception:native=None
                hard_required=bool(native and not native.null and not native.blank and not native.has_default() and not item.default_value)
                required=prior.get('required',False) if key in PROTECTED else item.required or hard_required
                if key in PROTECTED or required:enabled=True
            fields[key] = {**prior, **{name: getattr(item, name) for name in
                ('label', 'field_type', 'required', 'enabled', 'readonly', 'position', 'placeholder',
                 'help_text', 'default_value', 'minimum', 'maximum', 'max_length')},
                'key': key, 'native': bool(item.native_name), 'in_primary': in_primary, 'enabled': enabled, 'required':required, 'roles':item.roles,
                'choices': [{'value': v, 'label': l} for v, l in choice_pairs(item)] or prior.get('choices', [])}
    columns = [{'key': item.key, **{name: getattr(item, name) for name in
                ('label', 'source', 'component_key', 'enabled', 'position', 'width', 'align', 'display',
                 'wrap', 'filterable', 'searchable')}} for item in section.columns.all()] if section.pk else []
    stages = [{'key': str(item.pk), **{name: getattr(item, name) for name in
               ('label', 'enabled', 'initial', 'position', 'status', 'create_task')},
               'owner': str(item.assignee) if item.assignee_id else item.assignee_role or 'مالک رکورد'}
              for item in section.stages.select_related('assignee')] if section.pk else []
    transitions = [{'key': str(item.pk), 'label': item.label, 'source': str(item.source_id),
                    'target': str(item.target_id), 'enabled': item.enabled, 'require_note': item.require_note, 'roles':item.roles}
                   for item in section.transitions.all()] if section.pk else []
    path = definition.get('path')
    live_url = internal_url(path + ('?tab=' + definition['tab'] if definition.get('tab') else '')) if path else (
        reverse('accounts:structure_data', args=[section.key]) if section.pk else '')
    from .builder_usage import decorate_preview
    from .behavior_service import prototypes,effective_options,empty_locked
    prototypes_map=prototypes(section)
    for field in fields.values():
        name=field['key'] if field['native'] else 'extra_'+field['key']
        prototype=prototypes_map.get(name)
        if prototype is not None:
            options=effective_options(section,name,prototype)
            if options:field['choices']=[{'value':option['key'],'label':option['label']} for option in options]
        if section.pk:
            field['inspector_url']=reverse('accounts:behavior_inspector',args=[section.key,name])
    protected=empty_locked(section)
    rules=[{'id':str(rule.pk),'label':rule.label,'source':rule.source,'operator':rule.operator,'value':rule.value,
            'action':rule.action,'target':rule.target,'argument':rule.argument,'multiple':isinstance(prototypes_map.get(rule.target),forms.MultipleChoiceField),'roles':rule.roles,'enabled':rule.enabled and not (rule.target in protected and rule.action in ('hide','optional','clear'))}
           for rule in section.behaviors.all()] if section.pk else []
    from crm.middleware import get_current_request
    from .permissions import get_user_role
    request=get_current_request()
    preview_role=get_user_role(request.user) if request and getattr(request,'user',None) and request.user.is_authenticated else 'admin'
    result=decorate_preview(section, {'primary_fields':primary_fields,'label': section.label, 'section_enabled':section.enabled, 'section_roles':section.roles, 'section_permission':section.permission, 'fields': list(fields.values()),
            'columns':columns,'stages':stages,'transitions':transitions,'page_size':section.page_size,'live_url':live_url,
            'preview_role':preview_role,'focus_field':focus_field,'behavior_rules':rules,'replace_form_logic':section.replace_form_logic})
    if section.pk:
        result['section_edit_url']=reverse('accounts:structure_section',args=[section.key])+'#section-settings'
        from .interface import catalog
        from .structure_registry import component_scopes
        paths={'info':'customers/hub_table_partial.html','products':'products/list.html','categories':'products/category_list.html','calls':'calls/list.html','invoices':'sales/list.html','employees':'hr/employee_list.html','tasks':'hr/task_list.html','leaves':'hr/leave_list.html','attendance':'hr/attendance_list.html','ads':'ads/ad_list.html','ad_sources':'ads/source_list.html','ad_platforms':'ads/platform_list.html','ad_processes':'ads/process_list.html','users':'accounts/user_list.html'}
        result['base_columns']=[{'key':key,'label':meta['label'],'component_key':key,'enabled':True,'width':130,'align':'right' if index==0 else 'center','source':'native:name' if index==0 else 'sample:text','edit_url':reverse('accounts:interface_edit',args=[key])+'?scope='+section.key}
            for index,(key,meta) in enumerate((pair for pair in catalog().items() if pair[1]['kind']=='column' and pair[1].get('path')==paths.get(section.key)))][:12]
        candidates=[(key,meta) for key,meta in catalog().items() if meta['kind']=='button' and section.key in component_scopes(key,meta) and any(word in meta['label'] for word in ('ثبت تماس','ذخیره','ثبت کالا','ثبت فاکتور','ثبت ارزیابی'))]
        if candidates:
            key,meta=candidates[0]
            result['submit_edit_url']=reverse('accounts:interface_edit',args=[key])+'?scope='+section.key
        for column in columns:column['edit_url']=reverse('accounts:structure_element_edit',args=[section.key,'column',section.columns.get(key=column['key']).pk])
        for stage in stages:stage['edit_url']=reverse('accounts:structure_element_edit',args=[section.key,'stage',int(stage['key'])])
    return result



def element_meta(kind):
    return {
        'field': ('ورودی فرم', 'نام، نوع و قواعد ورود اطلاعات را تنظیم کنید.', 'fields'),
        'column': ('ستون و فیلتر', 'محتوای ستون و نحوه پیدا کردن اطلاعات را تنظیم کنید.', 'columns'),
        'stage': ('مرحله فرآیند', 'وضعیت، مسئول و وظیفه این مرحله را تعیین کنید.', 'workflow'),
        'transition': ('اقدام بین مراحل', 'مسیر مجاز حرکت کار را مشخص کنید.', 'workflow'),
    }[kind]


def section_cards(sections):
    descriptions = {
        'info': ('فرم تماس و مشخصات اولیه افراد', 'fields'),
        'reception': ('ورود مراجعه‌کننده و ارجاع کار', 'workflow'),
        'case': ('اطلاعات پرونده و ادامه رسیدگی', 'fields'),
        'registration': ('تکمیل مشخصات و اطلاعات نهایی', 'fields'),
        'hiring': ('مراحل مصاحبه و نتیجه استخدام', 'workflow'),
        'invoices': ('اطلاعات و فهرست فاکتورها', 'columns'),
        'tasks': ('فهرست وظایف و مسیر انجام کار', 'workflow'),
    }
    result = list(sections)
    for section in result:
        section.builder_category = 'custom' if section.custom else ('customers' if section.key in
            ('info','reception','case','registration','hiring','calls','invoices') else 'hr' if section.key in
            ('employees','tasks','leaves','attendance') else 'system' if section.key=='users' else 'business')
        from .builder_usage import usage
        section.builder_usage=usage('hidden','بخش غیرفعال') if not section.enabled else usage('conditional','فعال · دسترسی محدود') if section.roles or section.permission else usage('used','بخش فعال')
        section.builder_description, section.builder_icon = descriptions.get(section.key, ('فرم، فهرست و تنظیمات این بخش', 'columns'))
    return result
