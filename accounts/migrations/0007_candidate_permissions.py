from django.db import migrations


def copy_overrides(apps, schema_editor):
    Override=apps.get_model('accounts','UserPermissionOverride');alias=schema_editor.connection.alias
    for source,targets in [('customers.hiring',['customers.candidate_view']),('calls.add',['customers.candidate_add','customers.candidate_view']),('customers.edit',['customers.candidate_edit'])]:
        for row in Override.objects.using(alias).filter(permission_key=source):
            for key in targets:
                Override.objects.using(alias).get_or_create(user_id=row.user_id,permission_key=key,defaults={'granted':row.granted})


class Migration(migrations.Migration):
    dependencies=[('accounts','0006_expand_communications_permissions')]
    operations=[migrations.RunPython(copy_overrides,migrations.RunPython.noop)]
