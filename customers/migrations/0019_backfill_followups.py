from django.db import migrations
from django.utils import timezone


def backfill_followups(apps, schema_editor):
    """
    پیگیری‌های قدیمی (که فقط در Call ثبت شده بودند) به مدل FollowUp منتقل می‌شوند:
      • Call با contact_type='followup' یا status='followup' → پیگیری انجام‌شده
      • مشتری با needs_followup=True و بدون هیچ رکورد → پیگیری باز با تاریخ ثبت مشتری
    """
    Customer = apps.get_model('customers', 'Customer')
    FollowUp = apps.get_model('customers', 'FollowUp')
    Call = apps.get_model('calls', 'Call')

    # ── پیگیری‌های انجام‌شده از تاریخچه تماس ──
    followup_calls = (Call.objects
                      .filter(customer__isnull=False)
                      .filter(**{'contact_type': 'followup'})
                      .order_by('call_date'))
    also_status = (Call.objects
                   .filter(customer__isnull=False, status='followup')
                   .order_by('call_date'))

    seen_calls = set()
    for call in list(followup_calls) + list(also_status):
        if call.pk in seen_calls:
            continue
        seen_calls.add(call.pk)

        due = getattr(call, 'follow_up_date', None) or call.call_date.date()
        FollowUp.objects.create(
            customer_id=call.customer_id,
            due_date=due,
            note=(call.notes or '')[:2000],
            is_done=True,
            done_at=call.call_date,
            done_note=(call.notes or '')[:2000],
            created_by_id=call.called_by_id or call.created_by_id,
        )

    # ── مشتری‌هایی که «نیاز به پیگیری» دارند ولی رکوردی ندارند ──
    for customer in Customer.objects.filter(needs_followup=True, is_deleted=False):
        has_any = FollowUp.objects.filter(customer_id=customer.pk).exists()
        has_open = FollowUp.objects.filter(customer_id=customer.pk, is_done=False).exists()
        if has_any and has_open:
            continue
        if has_open:
            continue
        if has_any:
            # فقط پیگیری بسته دارد ولی پرچم روشن است → یک پیگیری باز لازم است
            pass
        FollowUp.objects.create(
            customer_id=customer.pk,
            due_date=customer.created_at.date() if customer.created_at else timezone.localdate(),
            note='پیگیری باز (انتقال از داده‌های قبلی)',
            is_done=False,
            created_by_id=customer.assigned_to_id or customer.created_by_id,
        )


def reverse_followups(apps, schema_editor):
    FollowUp = apps.get_model('customers', 'FollowUp')
    FollowUp.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0018_recordupdate'),
        ('calls', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill_followups, reverse_followups),
    ]
