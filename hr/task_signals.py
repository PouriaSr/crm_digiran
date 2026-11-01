from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from .models import Task


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
        def update_flag():
            from customers.models import Customer
            current = Customer.all_objects.filter(pk=instance.pk).first()
            if current:
                service.sync_customer_flag(current)
        from django.db import transaction
        transaction.on_commit(update_flag)
        for item in instance.followups.filter(is_done=False):
            service.sync_followup(item)
        for item in instance.receptions.filter(workflow_version=2, registration_completed_at__isnull=True):
            service.sync_reception(item)
        for item in instance.calls.filter(status='followup', is_followed_up=False):
            service.sync_call(item)
        for item in instance.invoices.filter(status__in=['draft', 'issued']):
            service.sync_invoice(item)


def workflow_deleted(sender, instance, **kwargs):
    labels = {'customers.FollowUp': 'followup', 'customers.Reception': 'case', 'customers.HiringApplication': 'interview', 'calls.Call': 'call', 'sales.Invoice': 'invoice', 'hr.LeaveRequest': 'leave'}
    kinds = [labels[sender._meta.label]]
    if sender._meta.label == 'customers.Reception':
        kinds.append('registration')
    for task in Task.objects.filter(source_type__in=kinds, source_id=instance.pk).exclude(status__in=['done', 'cancelled']):
        task.status = 'cancelled'
        task.save()


for label in ['customers.FollowUp', 'customers.Reception', 'customers.HiringApplication', 'customers.InterviewSession', 'customers.CaseWorkSession', 'customers.Customer', 'calls.Call', 'sales.Invoice', 'hr.LeaveRequest']:
    post_save.connect(workflow_changed, sender=label, dispatch_uid='hr.workflow.'+label)
    if label not in ['customers.Customer', 'customers.InterviewSession', 'customers.CaseWorkSession']:
        post_delete.connect(workflow_deleted, sender=label, dispatch_uid='hr.workflow_deleted.'+label)


from django.contrib.auth.models import User
from django.db.models.signals import m2m_changed
from django.db import transaction


def membership_changed(sender, instance, action, **kwargs):
    if action in ('post_add', 'post_remove', 'post_clear'):
        from .task_automation import backfill
        transaction.on_commit(backfill)


m2m_changed.connect(membership_changed, sender=User.groups.through, dispatch_uid='hr.task_role_change')
