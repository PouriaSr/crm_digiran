from django.db import migrations, models


def configure_melipayamak(apps, schema_editor):
    Config = apps.get_model('communications', 'ChannelConfiguration')
    alias = schema_editor.connection.alias
    config, _ = Config.objects.using(alias).get_or_create(
        channel='sms',
        defaults={
            'provider': 'melipayamak', 'sender': '', 'credential_env': 'MELLIPAYAMAK_API_KEY',
            'connection': {}, 'message_template': 'سلام {customer_name}،\n{task_title}\n{company_name}',
        },
    )
    connection = dict(config.connection or {})
    connection.update({
        'endpoint': 'https://rest.payamak-panel.com/api/SendSMS/SendSMS',
        'username_env': 'MELLIPAYAMAK_USERNAME',
    })
    config.provider = 'melipayamak'
    config.credential_env = 'MELLIPAYAMAK_API_KEY'
    config.connection = connection
    config.save(using=alias, update_fields=['provider', 'credential_env', 'connection'])


class Migration(migrations.Migration):
    dependencies = [('communications', '0002_testrun_custom_text_and_more')]

    operations = [
        migrations.AddField(
            model_name='testrun', name='provider_reference',
            field=models.CharField(blank=True, max_length=255, verbose_name='شناسه سرویس'),
        ),
        migrations.AddField(
            model_name='testrun', name='request_token',
            field=models.CharField(blank=True, max_length=64, null=True, unique=True, verbose_name='شناسه درخواست'),
        ),
        migrations.AlterField(
            model_name='testrun', name='kind',
            field=models.CharField(
                choices=[('live', 'ارسال واقعی'), ('message', 'پیش‌نمایش پیام'),
                         ('configuration', 'بررسی اتصال')], max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name='testrun', name='status',
            field=models.CharField(
                choices=[('sent', 'ارسال شد'), ('verified', 'اتصال تأیید شد'),
                         ('simulated', 'پیش‌نمایش شد'), ('incomplete', 'ناموفق یا ناقص')], max_length=16,
            ),
        ),
        migrations.RunPython(configure_melipayamak, migrations.RunPython.noop),
    ]
