"""Waiting people and reception assignments exist before a recorded visit."""
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
    records=person.receptions.filter(person_type='interviewer' if person.is_interviewer else 'customer')
    return records.annotate(task_arrival=Coalesce('hiring__current_arrived_at','arrived_at','created_at')).order_by('-task_arrival','-pk').first()


def needs_arrival(rec):
    if not rec or rec.workflow_version == 1 or (rec.registration_completed_at and rec.case_completed_at):
        return True
    app = getattr(rec, 'hiring', None)
    return bool(app and app.status == 'repeat' and app.latest_session_id and app.latest_session.saved_at
                and rec.task_arrival <= app.latest_session.saved_at)


def eligible_receivers():
    from django.contrib.auth.models import User
    users=User.objects.filter(is_active=True).prefetch_related('groups','permission_overrides').order_by('pk')
    return sorted([user for user in users if can_receive(user)],key=lambda user:(get_user_role(user) != ROLE_SECRETARY,user.pk))


def reconcile(person, request=False, receivers=None):
    from .task_automation import sync
    visit = latest_visit(person)
    owner = person.assigned_to
    waiting = bool(not person.is_deleted and not visit)
    if waiting:
        request=True
        if not can_receive(owner):
            pool=eligible_receivers() if receivers is None else receivers
            owner=next(iter(pool),None)
    description='فرد در انتظار پذیرش است؛ هنگام مراجعه، ورود واقعی او را در تب پذیرش ثبت کنید. واگذاری به معنی ثبت ورود نیست.'
    for task in Task.objects.filter(source_type='admission',source_customer=person).exclude(status__in=['done','cancelled']).select_related('assigned_user'):
        arrived = bool(visit and (task.source_key == f'admission:{person.pk}:first' or visit.task_arrival >= task.created_at))
        state = 'cancelled' if person.is_deleted else 'done' if arrived else 'pending' if waiting or can_receive(owner) else 'cancelled'
        sync(task.source_key, 'admission', person, 'ثبت ورود در پذیرش — '+person.name, task.assigned_user if arrived else owner, state, person,
             description=description,allow_unassigned=waiting or arrived)
    if not request or person.is_deleted or not (waiting or can_receive(owner)) or not needs_arrival(visit):
        return None
    token = sha256(f'{visit.pk}:{visit.task_arrival.isoformat()}'.encode()).hexdigest()[:20] if visit else 'first'
    return sync(f'admission:{person.pk}:{token}', 'admission', person, 'ثبت ورود در پذیرش — '+person.name,
                owner, 'pending', person,
                description=description,allow_unassigned=waiting)


def assignment_context(user, users=None):
    from django.contrib.auth.models import User
    from customers.access import is_card_manager
    if not is_card_manager(user) or not has_permission(user,'customers.admission_assign'):
        return {}
    if users is None:
        users=User.objects.filter(is_active=True).prefetch_related('groups','permission_overrides').order_by('first_name','username')
    return {'admission_assignees':[item for item in users if can_receive(item)], 'admission_default_user':user, 'can_choose_admission':has_permission(user,'customers.admission_choose')}


def backfill_assignments():
    from django.db.models import Q, Exists, OuterRef
    from accounts.permissions import ROLE_TO_GROUP
    from customers.models import Customer, Reception
    active=Task.objects.filter(source_type='admission').exclude(status__in=['done','cancelled']).values('source_customer_id')
    people=Customer.all_objects.alias(has_admission=Exists(Reception.objects.filter(customer_id=OuterRef('pk')).filter(Q(person_type='interviewer',customer__is_interviewer=True)|Q(person_type='customer',customer__is_interviewer=False)))).filter(Q(is_deleted=False,has_admission=False) | Q(assigned_to__groups__name__in=[ROLE_TO_GROUP[ROLE_SECRETARY],ROLE_SECRETARY]) | Q(pk__in=active)).distinct().select_related('assigned_to').prefetch_related('assigned_to__groups','assigned_to__permission_overrides')
    receivers=eligible_receivers()
    for person in people.iterator(chunk_size=200):
        reconcile(person,request=automatic_receiver(person.assigned_to),receivers=receivers)
