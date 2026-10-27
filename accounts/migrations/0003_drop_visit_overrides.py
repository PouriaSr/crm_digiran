from django.db import migrations


def drop_visit_overrides(apps, schema_editor):
    UserPermissionOverride = apps.get_model('accounts', 'UserPermissionOverride')
    UserPermissionOverride.objects.filter(permission_key='customers.visit').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(drop_visit_overrides, migrations.RunPython.noop),
    ]
