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
        records = records.filter(scope)
    return restrict_hiring_tasks(records, user)


def overdue_condition(now=None):
    """Date-only tasks expire the next day; appointments expire at their local time."""
    from django.utils import timezone

    when = timezone.localtime(now or timezone.now())
    return (
        Q(due_date__lt=when.date())
        | Q(due_date=when.date(), due_time__lt=when.time().replace(tzinfo=None))
    ) & ~Q(status__in=['done', 'cancelled'])
