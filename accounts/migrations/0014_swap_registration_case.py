from django.db import migrations


PAIRS={'customers.case':'customers.registration','customers.registration':'customers.case',
       'customers.case_edit':'customers.registration_edit','customers.registration_edit':'customers.case_edit'}


def swap(apps,schema_editor):
    alias=schema_editor.connection.alias
    Schema=apps.get_model('accounts','SectionSchema')
    defaults={row.key:{name:(PAIRS.get(getattr(row,name),getattr(row,name)) if name=='permission' else getattr(row,name)) for name in ('position','enabled','roles','permission')} for row in Schema.objects.using(alias).filter(key__in=['case','registration'])}
    Override=apps.get_model('accounts','UserPermissionOverride')
    for old in PAIRS:Override.objects.using(alias).filter(permission_key=old).update(permission_key='swap50:'+old)
    for old,new in PAIRS.items():Override.objects.using(alias).filter(permission_key='swap50:'+old).update(permission_key=new)
    Schema=apps.get_model('accounts','SectionSchema');Component=apps.get_model('accounts','InterfaceComponent')
    for Model in (Schema,Component):
        for item in Model.objects.using(alias).filter(permission__in=PAIRS):
            item.permission=PAIRS[item.permission];item.save(using=alias,update_fields=['permission'])
    for Model,keys in ((Schema,('case','registration')),(Component,('hub.tab.case','hub.tab.registration'))):
        left=Model.objects.using(alias).filter(key=keys[0]).first();right=Model.objects.using(alias).filter(key=keys[1]).first()
        if Model==Component and left is None and right is None:continue
        if Model==Component:
            if left is None and 'case' in defaults:left=Component(key=keys[0],kind='tab',section='مرکز مشتریان',label='پرونده',**defaults['case'])
            if right is None and 'registration' in defaults:right=Component(key=keys[1],kind='tab',section='مرکز مشتریان',label='ثبت اطلاعات',**defaults['registration'])
        if left and right:
            for name in ('position','enabled','roles','permission'):
                old=getattr(left,name);setattr(left,name,getattr(right,name));setattr(right,name,old)
            left.revision+=1;right.revision+=1
            left.save(using=alias);right.save(using=alias)
    locked=Component.objects.using(alias).filter(key='ui.customers.hub.button1').first()
    if locked:
        if locked.label=='🔒 ثبت اطلاعات':locked.label='🔒 پرونده'
        policy=Schema.objects.using(alias).filter(key='case').first()
        if policy:locked.position=policy.position
        locked.revision+=1;locked.save(using=alias)


class Migration(migrations.Migration):
    dependencies=[('accounts','0013_option_behavior_builder'),('customers','0028_registration_before_case')]
    operations=[migrations.RunPython(swap,swap)]
