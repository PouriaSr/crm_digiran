from django.db import migrations


def sync_call_followups(apps, schema_editor):
    """
    پیگیری‌هایی که با مدل جدید بسته شده‌اند، روی Call هم علامت‌گذاری می‌شوند تا
    تیک «پیگیری انجام شد» در ویرایش و برچسب تاریخچه با وضعیت لیست یکی باشد.
    """
    Call = apps.get_model('calls', 'Call')
    FollowUp = apps.get_model('customers', 'FollowUp')

    for call in Call.objects.filter(**{'contact_type': 'followup'}):
        changed = False

        if not call.is_followed_up:
            call.is_followed_up = True
            changed = True

        if not call.follow_up_date:
            fu = (FollowUp.objects
                  .filter(customer_id=call.customer_id, is_done=True)
                  .order_by('-done_at', '-id').first())
            call.follow_up_date = (fu.due_date if fu else call.call_date.date())
            changed = True

        if changed:
            call.save(update_fields=['is_followed_up', 'follow_up_date'])


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0019_backfill_followups'),
        ('calls', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(sync_call_followups, reverse),
    ]
