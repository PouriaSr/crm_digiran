from django.db import migrations
from django.utils import timezone


def populate_tasks(apps,schema_editor):
    alias=schema_editor.connection.alias
    Session=apps.get_model('customers','InterviewSession')
    Employee=apps.get_model('hr','Employee')
    Task=apps.get_model('hr','Task')
    employees=dict(Employee.objects.using(alias).exclude(user_id=None).values_list('user_id','pk'))
    sessions=Session.objects.using(alias).filter(result='repeat',saved_at__isnull=False,next_interview_at__isnull=False).select_related('application__reception__customer')
    for source in sessions.iterator(chunk_size=300):
        if Task.objects.using(alias).filter(hiring_session_id=source.pk).exists():continue
        application=source.application
        successor=Session.objects.using(alias).filter(application_id=application.pk,round_number__gt=source.round_number).order_by('round_number').first()
        state='done' if successor and successor.saved_at else 'in_progress' if successor else 'pending' if application.latest_session_id==source.pk and application.status=='repeat' else 'cancelled'
        when=timezone.localtime(source.next_interview_at)
        customer=application.reception.customer
        Task.objects.using(alias).create(title=('مصاحبه مجدد — '+customer.name)[:200],description='تسک ایجادشده از موعد مصاحبه ثبت‌شده قبلی.',assigned_user_id=customer.assigned_to_id,assigned_to_id=employees.get(customer.assigned_to_id),created_by_id=source.saved_by_id or source.interviewer_id,hiring_session_id=source.pk,performed_session_id=successor.pk if successor else None,due_date=when.date(),due_time=when.time().replace(tzinfo=None),priority='high',status=state,completed_at=successor.ended_at if successor and successor.saved_at else None)


class Migration(migrations.Migration):
    dependencies=[('hr','0006_task_assigned_user_task_due_time_task_hiring_session_and_more')]
    operations=[migrations.RunPython(populate_tasks,migrations.RunPython.noop)]
