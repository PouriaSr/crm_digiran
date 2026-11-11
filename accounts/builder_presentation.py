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
        ('دسترسی و فرآیند پیشرفته', '', 'roles,permission,gate_save', True),
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
        ('عملکرد و راهنما', '', 'action_kind,destination,url,body,confirmation,tooltip', False),
        ('دسترسی و جایگاه پیشرفته', '', 'roles,permission,position,scope_path', True),
    ],
}


def editor_groups(form, kind):
    result = []
    for title, hint, names, advanced in GROUPS[kind]:
        fields = [form[name] for name in names.split(',') if name in form.fields]
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
    if isinstance(field, forms.ChoiceField): return 'choice'
    if isinstance(field, forms.EmailField): return 'email'
    if isinstance(field, forms.URLField): return 'url'
    if isinstance(field.widget, forms.Textarea): return 'longtext'
    return 'text'


def section_preview(section):
    """Only field definitions and synthetic examples; no customer/task values."""
    fields = {}
    definition = SECTIONS.get(section.key, {})
    paths = definition.get('forms', [])
    # The main information entry point is the new-contact form.
    for path in paths[-1:]:
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
                            'required': field.required, 'enabled': True, 'readonly': False,
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
                model=getattr(getattr(import_string(paths[-1]),'_meta',None),'model',None)
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
    return decorate_preview(section, {'primary_fields':primary_fields,'label': section.label, 'section_enabled':section.enabled, 'section_roles':section.roles, 'section_permission':section.permission, 'fields': list(fields.values()), 'columns': columns,
            'stages': stages, 'transitions': transitions, 'page_size': section.page_size,
            'live_url': live_url})


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
