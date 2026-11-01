"""Recruitment appointments use the existing task registry and user ownership."""
from django.utils import timezone
from hr.models import Employee, Task


def owner_fields(user):
    return {'assigned_user': user, 'assigned_to': Employee.objects.filter(user=user).first() if user else None}


def sync_interview_task(session, actor):
    task = Task.objects.filter(hiring_session=session).first()
    if session.result != 'repeat' or not session.next_interview_at:
        if task and not task.performed_session_id and task.status != 'cancelled':
            task.status = 'cancelled'
            task.save(update_fields=['status','completed_at','updated_at'])
        return task
    if task and task.performed_session_id:
        return task
    rec = session.application.reception
    when = timezone.localtime(session.next_interview_at)
    values = {'title': ('مصاحبه مجدد — '+rec.customer.name)[:200],
              'description':'جلسه بعدی استخدام؛ اطلاعات کامل در پرونده کارجو قرار دارد.',
              'due_date':when.date(), 'due_time':when.time().replace(tzinfo=None),
              'status':'pending', 'priority':'high', **owner_fields(rec.customer.assigned_to)}
    if task:
        for key,value in values.items():setattr(task,key,value)
        task.save()
    else:
        task = Task.objects.create(hiring_session=session,created_by=actor,**values)
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
    Task.objects.filter(hiring_session__application=application,status__in=['pending','in_progress']).update(**owner_fields(user))
