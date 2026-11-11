"""Describe configured placement separately from conditional runtime visibility."""
from .structure_registry import SECTIONS
from .structure_forms_runtime import PROTECTED


def usage(state, label, note=''):
    return {'state': state, 'label': label, 'note': note}


def field_usage(field, section):
    if not field.get('in_primary', True):
        return usage('other', 'فرم دیگر این بخش', 'این ورودی در فرم اصلیِ پیش‌نمایش نیست؛ قواعد آن در فرم مرتبط اعمال می‌شود.')
    if not field.get('enabled', True):
        return usage('hidden', 'پنهان از فرم', 'این ورودی در فرم اصلی نمایش داده نمی‌شود؛ اطلاعات قبلی حفظ می‌شود.')
    if not section.enabled:
        return usage('hidden', 'بخش غیرفعال', 'ابتدا خود بخش را فعال کنید.')
    if field.get('roles') or section.roles or section.permission:
        return usage('conditional', 'در فرم · مشروط', 'در فرم اصلی قرار دارد؛ نمایش به نقش و مجوز کاربر وابسته است.')
    return usage('used', 'در فرم اصلی', 'در فرم اصلی قرار دارد؛ قواعد شرطی خود فرم همچنان برقرارند.')


def decorate_preview(section, preview):
    """Mutates only presentation dictionaries, never definitions or business data."""
    fields={field['key']: field for field in preview['fields']}
    for field in fields.values():field['usage']=field_usage(field,section)
    native_sources=set(SECTIONS.get(section.key,{}).get('fields',[]))
    for column in preview['columns']:
        source=column['source']
        field=fields.get(source[6:]) if source.startswith('extra:') else None
        available=(source=='system:record' or source.startswith('native:') and source[7:] in native_sources or
                   field is not None and not field.get('native') and field.get('enabled'))
        if not section.enabled or not column['enabled']:
            state=usage('hidden','پنهان از فهرست')
        elif not available:state=usage('unavailable','منبع غیرفعال','منبع این ستون حذف، پنهان یا نامعتبر شده است.')
        elif section.roles or section.permission or field and field.get('roles'):
            state=usage('conditional','در فهرست · مشروط','نمایش برای نقش‌های مجاز و با مجوز داده اصلی است.')
        else:state=usage('used','در فهرست','طبق تنظیمات ستون؛ مجوز داده و شرایط صفحه همچنان بررسی می‌شود.')
        column['usage']=state
        active=state['state'] in ('used','conditional')
        column['filter_usage']=usage('used','فیلتر فعال') if active and column['filterable'] else usage('hidden','بدون فیلتر فعال')
        column['search_usage']=usage('used','جستجو فعال') if active and column['searchable'] else usage('hidden','جستجو غیرفعال')
    stages={stage['key']: stage for stage in preview['stages']}
    reachable={key for key,stage in stages.items() if stage['enabled'] and stage['initial']}
    initial=bool(reachable)
    changed=True
    while changed:
        changed=False
        for transition in preview['transitions']:
            target=stages.get(transition['target'])
            if transition['enabled'] and transition['source'] in reachable and target and target['enabled'] and target['key'] not in reachable:
                reachable.add(target['key']);changed=True
    for key,stage in stages.items():
        if not section.enabled or not stage['enabled']:state=usage('hidden','مرحله غیرفعال')
        elif key not in reachable:state=usage('unlinked','به مسیر وصل نیست' if initial else 'مرحله شروع ندارد')
        else:state=usage('used','در مسیر فرآیند')
        stage['usage']=state
    for transition in preview['transitions']:
        source,target=stages.get(transition['source']),stages.get(transition['target'])
        if not section.enabled or not transition['enabled'] or not source or not target or not source['enabled'] or not target['enabled']:
            state=usage('hidden','مسیر غیرفعال')
        elif source['key'] not in reachable:state=usage('unlinked','به شروع وصل نیست')
        elif transition.get('roles'):state=usage('conditional','در مسیر · مشروط به نقش')
        else:state=usage('used','در مسیر فرآیند')
        transition['usage']=state
    return preview


def native_inventory(section, preview):
    from django import forms
    from django.utils.module_loading import import_string
    fields={field['key']:field for field in preview['fields']}
    rules={field.native_name:field for field in section.fields.all() if field.native_name}
    inventory={}
    for path in SECTIONS.get(section.key,{}).get('forms',[]):
        for name,field in import_string(path).base_fields.items():
            if name.startswith('password') or name=='id' or isinstance(field.widget,forms.HiddenInput):continue
            source=fields.get(name)
            inventory.setdefault(name,{'name':name,'label':source['label'] if source else str(field.label or name),
                'rule':rules.get(name),'primary':bool(source and source.get('in_primary',True) and source.get('enabled')),
                'usage':source['usage'] if source else usage('other','فرم دیگر این بخش')})
    return sorted(inventory.values(),key=lambda item:(not item['primary'],item['usage']['state']=='hidden'))


def annotate_components(section, rows, preview, overrides):
    fields={field['key']:field for field in preview['fields']}
    columns={column['component_key']:column for column in preview['columns'] if column['component_key']}
    primary_forms=SECTIONS.get(section.key,{}).get('forms',[])[-1:]
    for row in rows:
        item=overrides.get(row['key'])
        mandatory=False
        if row['key'].startswith('field.'):
            form_path,name=row['key'][6:].rsplit('.',1)
            field=fields.get(name)
            mandatory=name in PROTECTED or field and field.get('required')
            state=field['usage'] if field and form_path in primary_forms else usage('other','فرم دیگر این بخش')
        elif row['key'] in columns:state=columns[row['key']]['usage']
        else:state=usage('used','فعال در این بخش' if row.get('custom') else 'جزء اصلی صفحه',
                         'طبق شرایط صفحه، وضعیت رکورد و مجوز اصلی عملیات نمایش داده می‌شود.')
        if not section.enabled:state=usage('hidden','بخش غیرفعال')
        elif item and not item.enabled and not mandatory:state=usage('hidden','پنهان شده')
        elif item and (item.roles or item.permission):state=usage('conditional','نمایش مشروط','نمایش به نقش و مجوز تعیین‌شده وابسته است.')
        row['visibility_locked']=bool(mandatory)
        row['usage']=state
        row['configured']=bool(item or row['key'] in columns)
    return rows
