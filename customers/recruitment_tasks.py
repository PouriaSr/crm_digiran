"""Recruitment appointments use the existing task registry and user ownership."""
from django.utils import timezone
from hr.models import Employee, Task


def owner_fields(user):
    return {'assigned_user': user, 'assigned_to': Employee.objects.filter(user=user).first() if user else None}


def sync_interview_task(session, actor):
    from hr.task_automation import choose_owner
    from django.db import transaction
    rec = session.application.reception
    user = choose_owner([rec.customer.assigned_to, rec.referred_to], 'customers.hiring_interview')
    with transaction.atomic():
        task = Task.objects.select_for_update().filter(hiring_session=session).first()
        valid = (session.saved_at and session.result == 'repeat' and session.next_interview_at
                 and not rec.customer.is_deleted and user
                 and (rec.referred_at or rec.workflow_version == 1))
        if not valid:
            if task and task.status not in ('done', 'cancelled'):
                task.status = 'cancelled'
                task.save(update_fields=['status', 'updated_at'])
            return task
        successor = session.application.sessions.filter(round_number__gt=session.round_number).order_by('round_number').first()
        state = 'done' if successor and successor.saved_at else 'in_progress' if successor else 'pending'
        if not task and state == 'done':
            return None
        when = timezone.localtime(session.next_interview_at)
        values = {'title': ('مصاحبه مجدد — '+rec.customer.name)[:200],
                  'description':'جلسه بعدی استخدام؛ اطلاعات کامل در پرونده کارجو قرار دارد.',
                  'due_date':when.date(), 'due_time':when.time().replace(tzinfo=None),
                  'status':state, 'priority':'high', 'source_customer':rec.customer,
                  'performed_session':successor, **owner_fields(user)}
        if task:
            if all(getattr(task,key)==value for key,value in values.items()):
                return task
            for key,value in values.items():setattr(task,key,value)
            if state == 'done':task.completed_at=successor.ended_at or successor.saved_at
            task.save()
        else:
            task, _ = Task.objects.get_or_create(hiring_session=session, defaults={**values, 'created_by':actor})
        return task


def begin_interview_task(application, session):
    task=Task.objects.select_for_update().filter(hiring_session_id=application.latest_session_id,status='pending',performed_session__isnull=True).first()
    if task:
        task.status='in_progress';task.performed_session=session
        task.save(update_fields=['status','performed_session','updated_at','completed_at'])


def finish_interview_task(session):
    task=Task.objects.select_for_update().filter(performed_session=session).first()
    if task and task.status!='done':
        task.status='done';task.completed_at=session.ended_at
        task.save(update_fields=['status','completed_at','updated_at'])


def reassign_interview_tasks(application, user):
    for task in Task.objects.filter(hiring_session__application=application,status__in=['pending','in_progress']):
        for key,value in owner_fields(user).items():setattr(task,key,value)
        task.save()
