from django.db import migrations


def enable_members(apps, schema_editor):
    Override = apps.get_model('accounts', 'UserPermissionOverride')
    Override.objects.using(schema_editor.connection.alias).filter(
        user__is_active=True, permission_key__in=['hr.view_tasks', 'hr.report_tasks'], granted=False
    ).update(granted=True)


class Migration(migrations.Migration):
    dependencies = [('hr', '0008_task_source_customer_task_source_id_task_source_key_and_more'), ('accounts', '0005_restrict_customer_deactivation')]
    operations = [migrations.RunPython(enable_members, migrations.RunPython.noop)]
