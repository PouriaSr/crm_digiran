"""Assignments to reception exist before a physical visit is recorded."""
from hashlib import sha256
from django.db.models.functions import Coalesce
from accounts.permissions import get_user_role, has_permission, ROLE_SECRETARY
from .models import Task


def can_receive(user):
    return bool(user and user.is_active and all(has_permission(user, key) for key in
        ('hr.view_tasks','customers.reception','customers.reception_add')))


def automatic_receiver(user):
    return bool(user and get_user_role(user) == ROLE_SECRETARY and can_receive(user))


def latest_visit(person):
    return person.receptions.annotate(task_arrival=Coalesce('hiring__current_arrived_at','arrived_at','created_at')).order_by('-task_arrival','-pk').first()


def needs_arrival(rec):
    if not rec or rec.workflow_version == 1 or rec.registration_completed_at:
        return True
    app = getattr(rec, 'hiring', None)
    return bool(app and app.status == 'repeat' and app.latest_session_id and app.latest_session.saved_at
                and rec.task_arrival <= app.latest_session.saved_at)


def reconcile(person, request=False):
    from .task_automation import sync
    visit = latest_visit(person)
    owner = person.assigned_to
    for task in Task.objects.filter(source_type='admission',source_customer=person).exclude(status__in=['done','cancelled']):
        state = 'cancelled' if person.is_deleted or not can_receive(owner) else 'done' if visit and visit.task_arrival >= task.created_at else 'pending'
        sync(task.source_key, 'admission', person, 'ثبت ورود در پذیرش — '+person.name, owner, state, person,
             description='فرد به شما واگذار شده است؛ هنگام مراجعه، ورود واقعی او را در تب پذیرش ثبت کنید. واگذاری به معنی ثبت ورود نیست.')
    if not request or person.is_deleted or not can_receive(owner) or not needs_arrival(visit):
        return None
    token = sha256(f'{visit.pk}:{visit.task_arrival.isoformat()}'.encode()).hexdigest()[:20] if visit else 'first'
    return sync(f'admission:{person.pk}:{token}', 'admission', person, 'ثبت ورود در پذیرش — '+person.name,
                owner, 'pending', person,
                description='فرد به شما واگذار شده است؛ هنگام مراجعه، ورود واقعی او را در تب پذیرش ثبت کنید. واگذاری به معنی ثبت ورود نیست.')


def assignment_context(user, users=None):
    from django.contrib.auth.models import User
    from customers.access import is_card_manager
    if not is_card_manager(user) or not has_permission(user,'customers.reassign'):
        return {}
    if users is None:
        users=User.objects.filter(is_active=True).prefetch_related('groups','permission_overrides').order_by('first_name','username')
    return {'admission_assignees':[item for item in users if can_receive(item)]}


def backfill_assignments():
    from django.db.models import Q
    from accounts.permissions import ROLE_TO_GROUP
    from customers.models import Customer
    active=Task.objects.filter(source_type='admission').exclude(status__in=['done','cancelled']).values('source_customer_id')
    people=Customer.all_objects.filter(Q(assigned_to__groups__name__in=[ROLE_TO_GROUP[ROLE_SECRETARY],ROLE_SECRETARY]) | Q(pk__in=active)).distinct().select_related('assigned_to').prefetch_related('assigned_to__groups','assigned_to__permission_overrides')
    for person in people.iterator(chunk_size=200):
        reconcile(person,request=automatic_receiver(person.assigned_to))
