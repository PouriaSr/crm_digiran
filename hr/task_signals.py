from django.db.models import Q
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from .models import Task


@receiver(pre_save, sender='customers.Customer', dispatch_uid='hr.task_assignment_before')
def customer_assignment_before(sender, instance, raw=False, **kwargs):
    if not raw:
        previous=sender.all_objects.filter(pk=instance.pk).values('assigned_to_id').first() if instance.pk else None
        instance._task_assignment_changed=not previous or previous['assigned_to_id'] != instance.assigned_to_id


@receiver(pre_save, sender=Task, dispatch_uid='hr.task_before')
def before_task(sender, instance, raw=False, **kwargs):
    if not raw:
        instance._task_before = Task.objects.select_related('assigned_user', 'assigned_to__user').filter(pk=instance.pk).first() if instance.pk else None


@receiver(post_save, sender=Task, dispatch_uid='hr.task_events')
def after_task(sender, instance, raw=False, **kwargs):
    if not raw:
        from .task_automation import record_change
        record_change(instance, getattr(instance, '_task_before', None))


def workflow_changed(sender, instance, raw=False, **kwargs):
    if raw:
        return
    from . import task_automation as service
    name = sender._meta.label
    functions = {'customers.FollowUp': service.sync_followup, 'customers.Reception': service.sync_reception,
                 'customers.HiringApplication': service.sync_hiring, 'calls.Call': service.sync_call,
                 'sales.Invoice': service.sync_invoice, 'hr.LeaveRequest': service.sync_leave}
    if name in functions:
        functions[name](instance)
    elif name == 'customers.CaseWorkSession':
        service.sync_reception(instance.reception)
    elif name == 'customers.InterviewSession':
        service.sync_hiring(instance.application)
    elif name == 'customers.Customer':
        from .admission_tasks import reconcile, automatic_receiver
        reconcile(instance, request=getattr(instance,'_task_assignment_changed',False) and automatic_receiver(instance.assigned_to))
        def update_flag():
            from customers.models import Customer
            current = Customer.all_objects.filter(pk=instance.pk).first()
            if current:
                service.sync_customer_flag(current)
        from django.db import transaction
        transaction.on_commit(update_flag)
        for item in instance.followups.filter(is_done=False):
            service.sync_followup(item)
        for item in instance.receptions.filter(workflow_version=2).filter(Q(registration_completed_at__isnull=True)|Q(case_completed_at__isnull=True)):
            service.sync_reception(item)
        from customers.models import HiringApplication
        for item in HiringApplication.objects.filter(reception__customer=instance):
            service.sync_hiring(item)
        for item in instance.calls.filter(status='followup', is_followed_up=False):
            service.sync_call(item)
        for item in instance.invoices.filter(status__in=['draft', 'issued']):
            service.sync_invoice(item)


def workflow_deleted(sender, instance, **kwargs):
    labels = {'customers.FollowUp': 'followup', 'customers.Reception': 'case', 'customers.HiringApplication': 'interview', 'customers.InterviewSession':'invitation', 'calls.Call': 'call', 'sales.Invoice': 'invoice', 'hr.LeaveRequest': 'leave'}
    kinds = [labels[sender._meta.label]]
    if sender._meta.label == 'customers.Reception':
        kinds.extend(['registration', 'reception'])
    for task in Task.objects.filter(source_type__in=kinds, source_id=instance.pk).exclude(status__in=['done', 'cancelled']):
        task.status = 'cancelled'
        task.save()


for label in ['customers.FollowUp', 'customers.Reception', 'customers.HiringApplication', 'customers.InterviewSession', 'customers.CaseWorkSession', 'customers.Customer', 'calls.Call', 'sales.Invoice', 'hr.LeaveRequest']:
    post_save.connect(workflow_changed, sender=label, dispatch_uid='hr.workflow.'+label)
    if label not in ['customers.Customer', 'customers.CaseWorkSession']:
        post_delete.connect(workflow_deleted, sender=label, dispatch_uid='hr.workflow_deleted.'+label)


from django.contrib.auth.models import User
from django.db.models.signals import m2m_changed
from django.db import transaction


def membership_changed(sender, instance, action, **kwargs):
    if action in ('post_add', 'post_remove', 'post_clear'):
        from .task_automation import schedule_backfill
        schedule_backfill()


m2m_changed.connect(membership_changed, sender=User.groups.through, dispatch_uid='hr.task_role_change')


def permission_changed(sender, instance, raw=False, **kwargs):
    if not raw and (instance.permission_key.startswith(('customers.', 'calls.', 'invoices.')) or instance.permission_key in ('hr.review_leaves','hr.view_tasks')):
        from .task_automation import schedule_backfill
        schedule_backfill()


post_save.connect(permission_changed, sender='accounts.UserPermissionOverride', dispatch_uid='hr.task_permission_change')
post_delete.connect(permission_changed, sender='accounts.UserPermissionOverride', dispatch_uid='hr.task_permission_delete')


@receiver(pre_save, sender=User, dispatch_uid='hr.task_user_access_before')
def user_access_before(sender, instance, raw=False, **kwargs):
    previous = User.objects.filter(pk=instance.pk).values('is_active','is_superuser').first() if instance.pk and not raw else None
    instance._task_access_changed = bool(previous and any(previous[key] != getattr(instance,key) for key in previous))


@receiver(post_save, sender=User, dispatch_uid='hr.task_user_access_after')
def user_access_after(sender, instance, raw=False, **kwargs):
    if not raw and getattr(instance, '_task_access_changed', False):
        from .task_automation import schedule_backfill
        schedule_backfill()
