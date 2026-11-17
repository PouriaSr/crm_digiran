from django.db import migrations


def configure_simple_send(apps, schema_editor):
    Config = apps.get_model('communications', 'ChannelConfiguration')
    Template = apps.get_model('communications', 'MessageTemplate')
    alias = schema_editor.connection.alias
    Config.objects.using(alias).filter(channel='sms', provider='melipayamak').update(
        credential_env='MELLIPAYAMAK_SIMPLE_API_URL',
        connection={'api_mode': 'console_simple'},
    )
    Template.objects.using(alias).get_or_create(
        channel='sms',
        name='ارسال آدرس',
        defaults={
            'category': 'custom',
            'body': 'سلام {customer_name} عزیز،\nآدرس {company_name}:\n{address}\nدر صورت نیاز با کارشناس خود، {expert_name}، در ارتباط باشید.',
            'is_active': True,
            'is_suggested': True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [('communications', '0003_alter_testrun_status')]

    operations = [
        migrations.RunPython(configure_simple_send, migrations.RunPython.noop),
    ]
