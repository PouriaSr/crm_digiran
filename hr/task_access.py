from django.db.models import Q

from accounts.permissions import has_permission


def restrict_hiring_tasks(records, user):
    """Apply dossier privacy wherever linked tasks are displayed."""
    from customers.access import is_card_manager

    ordinary = Q(hiring_session__isnull=True)
    if not has_permission(user, 'customers.hiring'):
        return records.filter(ordinary)
    if not is_card_manager(user):
        records = records.filter(
            ordinary | Q(hiring_session__application__reception__customer__assigned_to=user)
        )
    return records.filter(
        ordinary | Q(hiring_session__application__reception__customer__is_deleted=False)
    )


def visible_tasks(user):
    from .models import Task

    records = Task.objects.all()
    if not has_permission(user, 'hr.manage_tasks'):
        employee = getattr(user, 'employee_profile', None)
        scope = Q(assigned_user=user)
        if employee:
            scope |= Q(assigned_to=employee)
        records = records.filter(scope | Q(events__report_user=user)).distinct()
    records = restrict_hiring_tasks(records, user)
    from customers.access import is_card_manager
    if not is_card_manager(user):
        records = records.filter(Q(source_type='') | Q(assigned_user=user) | Q(events__report_user=user)).distinct()
    permissions = {'customer_followup':'customers.followup', 'followup':'customers.followup', 'case':'customers.case', 'registration':'customers.registration', 'interview':'customers.hiring', 'call':'calls.view', 'invoice':'invoices.view', 'leave':'hr.review_leaves'}
    for kind, permission in permissions.items():
        if not has_permission(user, permission):
            records = records.exclude(source_type=kind)
    if not is_card_manager(user):
        records = records.exclude(Q(source_type__in=['case','registration','interview','followup','customer_followup','call']) & ~Q(source_customer__assigned_to=user) & Q(source_customer__isnull=False))
    records = records.exclude(source_customer__is_deleted=True)
    return records


def overdue_condition(now=None):
    """Date-only tasks expire the next day; appointments expire at their local time."""
    from django.utils import timezone

    when = timezone.localtime(now or timezone.now())
    return (
        Q(due_date__lt=when.date())
        | Q(due_date=when.date(), due_time__lt=when.time().replace(tzinfo=None))
    ) & ~Q(status__in=['done', 'cancelled'])


def owned_tasks(user):
    from .models import Task
    return Task.objects.filter(Q(assigned_user=user) | Q(assigned_user__isnull=True, assigned_to__user=user))


def source_url(task):
    from django.urls import reverse
    from urllib.parse import urlencode
    if task.hiring_session_id:
        return task.recruitment_url
    if task.source_type in ('case', 'registration'):
        return reverse('customers:hub') + '?' + urlencode({'tab': task.source_type, 'r': task.source_id})
    if task.source_type == 'interview':
        from customers.models import HiringApplication
        rec = HiringApplication.objects.filter(pk=task.source_id).values_list('reception_id', flat=True).first()
        return reverse('customers:hub') + '?' + urlencode({'tab': 'hiring', 'r': rec})
    if task.source_type in ('followup','customer_followup'):
        return reverse('customers:hub') + '?' + urlencode({'tab': 'info', 'q': task.source_customer.mobile if task.source_customer else ''})
    if task.source_type == 'call':
        return reverse('calls:detail', args=[task.source_id])
    if task.source_type == 'invoice':
        return reverse('sales:detail', args=[task.source_id])
    if task.source_type == 'leave':
        return reverse('hr:leave_review', args=[task.source_id])
    return reverse('hr:task_detail', args=[task.pk])
