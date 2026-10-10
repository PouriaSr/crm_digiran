from django.db import migrations


def fix_contradictions(apps, schema_editor):
    """اصلاح رکوردهایی که تناقض دارن"""
    Call = apps.get_model('calls', 'Call')

    # رکوردهایی که status='followup' ولی is_followed_up=True هستن
    fixed = Call.objects.filter(
        status='followup',
        is_followed_up=True
    ).update(is_followed_up=False)

    if fixed:
        print(f'✅ {fixed} رکورد اصلاح شد')


class Migration(migrations.Migration):

    dependencies = [
        ('calls', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(fix_contradictions, migrations.RunPython.noop),
    ]