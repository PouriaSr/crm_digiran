from django.db import migrations


def copy_existing_communications_overrides(apps, schema_editor):
    Override = apps.get_model('accounts', 'UserPermissionOverride')
    alias = schema_editor.connection.alias
    mappings = {
        'communications.view': (
            'communications.configuration', 'communications.templates', 'communications.history',
        ),
        'communications.manage': ('communications.manage_templates',),
    }
    for source, targets in mappings.items():
        for item in Override.objects.using(alias).filter(permission_key=source):
            for target in targets:
                Override.objects.using(alias).get_or_create(
                    user_id=item.user_id, permission_key=target, defaults={'granted': item.granted},
                )


class Migration(migrations.Migration):
    dependencies = [('accounts', '0005_restrict_customer_deactivation')]
    operations = [migrations.RunPython(copy_existing_communications_overrides, migrations.RunPython.noop)]
