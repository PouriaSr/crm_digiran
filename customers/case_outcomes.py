"""A visit's cancellation and follow-up stay separate from the shared case form."""
from django.contrib.auth.models import User
from django.utils import timezone
from accounts.permissions import get_user_role, has_permission, ROLE_SALES
from .access import can_edit_card


def eligible_sales(user):
    return bool(user and user.is_active and get_user_role(user) == ROLE_SALES and
                all(has_permission(user, key) for key in ('customers.info', 'customers.followup', 'calls.add', 'hr.view_tasks')))


def sales_choices():
    ids = [u.pk for u in User.objects.filter(is_active=True).prefetch_related('groups', 'permission_overrides')
           if eligible_sales(u)]
    return User.objects.filter(pk__in=ids).order_by('first_name', 'username')


def save_outcome(rec, case, sales, actor):
    old = (rec.case_result, rec.case_cancel_reason, rec.case_result_notes)
    old_owner_id = rec.case_followup_owner_id
    rec.case_result, rec.case_cancel_reason, rec.case_result_notes = case.visit_result, case.cancel_reason, case.result_notes
    if case.visit_result == 'abandoned' and has_permission(actor, 'customers.case_refer'):
        rec.case_followup_owner = sales
        if sales and rec.customer.assigned_to_id != sales.pk:
            rec.customer.assigned_to = sales
            rec.customer.save(update_fields=['assigned_to', 'updated_at'])
    if old != (rec.case_result, rec.case_cancel_reason, rec.case_result_notes) or old_owner_id != rec.case_followup_owner_id:
        rec.case_followup_done_at = None
    if old_owner_id != rec.case_followup_owner_id:
        from .models import RecordUpdate
        old_owner = User.objects.filter(pk=old_owner_id).first() if old_owner_id else None
        RecordUpdate.objects.create(customer=rec.customer, scope='case', edited_by=actor, changes=[{
            'label': 'کارشناس پیگیری انصراف',
            'old': (old_owner.get_full_name() or old_owner.username) if old_owner else '',
            'new': (sales.get_full_name() or sales.username) if sales else '',
        }])
    rec.save(update_fields=['case_result', 'case_cancel_reason', 'case_result_notes',
                            'case_followup_owner', 'case_followup_done_at', 'updated_at'])


def sync_case_followup(rec):
    from hr.task_automation import sync
    valid = rec.person_type == 'customer' and not rec.customer.is_interviewer and rec.case_result == 'abandoned' and rec.case_completed_at and rec.case_followup_owner_id
    from hr.models import Task
    key = 'case_followup:' + str(rec.pk)
    existing = Task.objects.filter(source_key=key).first()
    if not valid and not existing:
        return
    owner = rec.case_followup_owner
    if owner and (not can_edit_card(owner, rec.customer) or not eligible_sales(owner)):
        owner = None
    from .models import CustomerCase
    reason = dict(CustomerCase.CANCEL_REASONS).get(rec.case_cancel_reason, rec.case_cancel_reason)
    task = sync(key, 'case_followup', rec, 'پیگیری انصراف — ' + rec.customer.name, owner,
         'cancelled' if not valid or rec.customer.is_deleted else 'done' if rec.case_followup_done_at else 'follow_up',
         customer=rec.customer, completed_at=rec.case_followup_done_at,
         date=existing.due_date if existing else None, time=existing.due_time if existing else None,
         description=existing.description if existing and not valid else 'دلیل کنسلی: ' + reason + '\nتوضیحات انصراف: ' + rec.case_result_notes +
                     '\nنتیجه پیگیری را از بخش اطلاعات مشتری ثبت کنید.')
    from hr.task_automation import sync_customer_flag
    sync_customer_flag(rec.customer)
    return task


def finish_case_followups(customer):
    from .models import Customer, Reception
    from django.db.models import F
    records = list(Reception.objects.filter(customer=customer, case_result='abandoned',
        case_followup_owner__isnull=False, case_followup_owner_id=F('customer__assigned_to_id'),
        case_followup_done_at__isnull=True))
    if not records:
        return
    # Clear the old undated flag before completing this source; a new scheduled
    # follow-up is still created normally by the contact form when requested.
    has_open = customer.followups.filter(is_done=False).exists() or customer.calls.filter(status='followup',is_followed_up=False).exists()
    Customer.all_objects.filter(pk=customer.pk).update(needs_followup=has_open)
    customer.needs_followup = has_open
    for rec in records:
        rec.case_followup_done_at = timezone.now()
        rec.save(update_fields=['case_followup_done_at', 'updated_at'])
