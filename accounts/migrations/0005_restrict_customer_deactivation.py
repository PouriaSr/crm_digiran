from django.db import migrations


def remove_out_of_role_grants(apps, schema_editor):
    overrides = apps.get_model('accounts', 'UserPermissionOverride')
    supervisors = ['مدیر فروش', 'سرپرست', 'supervisor', 'sales_manager']
    overrides.objects.using(schema_editor.connection.alias).filter(
        permission_key='customers.delete', granted=True,
    ).exclude(user__is_superuser=True).exclude(user__groups__name__in=supervisors).delete()


class Migration(migrations.Migration):
    dependencies = [('accounts', '0004_userroleprofile')]
    operations = [migrations.RunPython(remove_out_of_role_grants, migrations.RunPython.noop)]
