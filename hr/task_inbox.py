"""Personal work queue. Reading an update never completes work or its report."""
from django.core.paginator import Paginator
from django.db.models import Count, Exists, Max, Min, OuterRef, Q
from django.urls import reverse
from django.utils import timezone
from accounts.permissions import get_user_permissions
from crm.pagination import PAGE_SIZE
from crm.numerals import digit_contains
from .models import Task, TaskEvent, TaskNotice
from .task_access import owned_tasks, source_url, visible_tasks, overdue_condition
from .task_filters import TaskQueueFilters, filter_task_dates, order_tasks, filter_task_properties, available_sources


def inbox_records(user):
    records = visible_tasks(user)
    work = records.filter(pk__in=owned_tasks(user).values('pk')).exclude(status__in=['done', 'cancelled'])
    events = TaskEvent.objects.filter(report_user=user, report_required=True, report__isnull=True, task__in=records)
    if 'hr.report_tasks' not in get_user_permissions(user):
        events = events.none()
    notices = TaskNotice.objects.filter(user=user, task__in=records)
    return records, work, events, notices


def inbox_counts(records, work, events, notices):
    # Aggregate a plain Task query; DISTINCT permission scopes stay in the subquery.
    flagged = Task.objects.filter(pk__in=records.values('pk')).alias(
        _personal_open=Exists(work.filter(pk=OuterRef('pk'))),
        _personal_report=Exists(events.filter(task_id=OuterRef('pk'))),
        _personal_update=Exists(notices.filter(task_id=OuterRef('pk'))),
        _personal_unread=Exists(notices.filter(task_id=OuterRef('pk'),read_at__isnull=True)),
    )
    return flagged.aggregate(
        attention=Count('pk',filter=Q(_personal_open=True)|Q(_personal_report=True),distinct=True),
        work=Count('pk',filter=Q(_personal_open=True),distinct=True),
        reports=Count('pk',filter=Q(_personal_report=True),distinct=True),
        updates=Count('pk',filter=Q(_personal_update=True),distinct=True),
        updates_unread=Count('pk',filter=Q(_personal_unread=True),distinct=True),
    )



def report_item(event):
    return {'event': event.pk, 'task': event.task_id, 'title': event.snapshot.get('title', event.task.title),
            'description': event.snapshot.get('description', event.task.description or ''),
            'status': dict(Task.STATUS_CHOICES).get(event.to_status, event.to_status),
            'when': timezone.localtime(event.created_at).isoformat(),
            'url': reverse('hr:task_detail', args=[event.task_id])}


def personal_inbox(user, params):
    records, work, events, notices = inbox_records(user)
    counts = inbox_counts(records, work, events, notices)
    today = timezone.localdate()
    late = overdue_condition()
    due_counts = {'all': counts['work'], 'overdue': work.filter(late).count(),
                  'today': work.filter(due_date=today).exclude(late).count(),
                  'upcoming': work.filter(due_date__gt=today).count(),
                  'undated': work.filter(due_date__isnull=True).count()}
    view = params.get('view', 'work')
    if view not in ('work', 'reports', 'updates'):
        view = 'work'
    due = params.get('due', 'all')
    if due not in due_counts:
        due = 'all'
    query = params.get('q', '').strip()[:200]
    queue_filters = TaskQueueFilters(params)
    valid_filters = queue_filters.is_valid()
    filter_data = queue_filters.cleaned_data if valid_filters else {}
    permissions = get_user_permissions(user)
    related = ('assigned_user', 'assigned_to', 'source_customer', 'hiring_session__application__reception')
    first_events = events.order_by().values('task_id').annotate(first=Min('pk')).values('first')
    latest_notices = notices.order_by().values('task_id').annotate(latest=Max('pk')).values('latest')
    if view == 'work':
        items = work
        if due == 'overdue':
            items = items.filter(late)
        elif due == 'today':
            items = items.filter(due_date=today).exclude(late)
        elif due == 'upcoming':
            items = items.filter(due_date__gt=today)
        elif due == 'undated':
            items = items.filter(due_date__isnull=True)
        if query:
            items = items.filter(digit_contains('title',query) | digit_contains('description',query))
        items = items.select_related(*related)
        items = order_tasks(items, filter_data.get('sort'))
    elif view == 'reports':
        items = events.filter(pk__in=first_events).select_related('task').order_by('pk')
        if query:
            items = items.filter(digit_contains('task__title',query) | digit_contains('task__description',query))
    else:
        items = notices.filter(pk__in=latest_notices).select_related('task').order_by('-pk')
        if query:
            # Match all changes of a task, then show its newest change.
            matching = notices.filter(digit_contains('task__title',query) | digit_contains('text',query)).values('task_id')
            items = items.filter(task_id__in=matching)
    if view != 'work':
        items = order_tasks(items, filter_data.get('sort'), 'task__')
    items = filter_task_properties(items,filter_data,'' if view == 'work' else 'task__')
    items = filter_task_dates(items, filter_data, '' if view == 'work' else 'task__') if valid_filters else items.none()
    page = Paginator(items, PAGE_SIZE).get_page(params.get('page', 1))
    rows = list(page)
    task_ids = [item.pk if view == 'work' else item.task_id for item in rows]
    pending_counts = dict(events.filter(task_id__in=task_ids).order_by().values('task_id').annotate(total=Count('pk')).values_list('task_id','total'))
    unread_counts = dict(notices.filter(task_id__in=task_ids,read_at__isnull=True).order_by().values('task_id').annotate(total=Count('pk')).values_list('task_id','total'))
    first_by_task = {event.task_id: event for event in events.filter(pk__in=first_events,task_id__in=task_ids).select_related('task')}
    payload = []
    action_permissions = {'admission':'customers.reception_add','reception':'customers.reception_refer','invitation':'customers.hiring_interview','case':'customers.case_edit','registration':'customers.registration_edit','interview':'customers.hiring_interview',
                          'followup':'customers.followup','customer_followup':'customers.followup','call':'calls.edit','invoice':'invoices.edit','leave':'hr.review_leaves'}
    for item in rows:
        task = item if view == 'work' else item.task
        row = {'task': task.pk, 'title': task.title, 'url': reverse('hr:task_detail',args=[task.pk]),
               'status': task.get_status_display(), 'status_key': task.status, 'report_count': pending_counts.get(task.pk,0), 'unread_count': unread_counts.get(task.pk,0)}
        if view == 'work':
            permission = 'customers.hiring_interview' if task.hiring_session_id else action_permissions.get(task.source_type,'hr.report_tasks')
            can_act=permission in permissions
            if task.source_type=='structure':
                from accounts.models import SectionRecord
                from accounts.structure_service import can_access
                configured=SectionRecord.objects.select_related('section').filter(pk=task.source_id).first()
                can_act=bool(configured and can_access(user,configured.section,True))
            row.update(description=(task.description or '')[:600], due_date=task.due_date.isoformat() if task.due_date else None,
                       due_time=task.due_time.strftime('%H:%M') if task.due_time else None, overdue=task.is_overdue,
                       priority=task.get_priority_display(), priority_key=task.priority,
                       manual=not task.source_type and not task.hiring_session_id, can_act=can_act,
                       action_url=source_url(task) if can_act else row['url'],
                       report=report_item(first_by_task[task.pk]) if task.pk in first_by_task else None)
        elif view == 'reports':
            row.update(report=report_item(item), when=timezone.localtime(item.created_at).isoformat())
        else:
            row.update(notice=item.pk, summary=item.text, when=timezone.localtime(item.created_at).isoformat(), unread=bool(unread_counts.get(task.pk)))
        payload.append(row)
    auto_reports = [report_item(event) for event in events.select_related('task').order_by('pk')[:PAGE_SIZE]]
    newest = notices.order_by('-pk').first()
    filter_scope=work if view=='work' else records.filter(pk__in=(events if view=='reports' else notices).values('task_id'))
    return {'filter_choices':{'source':available_sources(filter_scope),'status':[(key,label) for key,label in Task.STATUS_CHOICES if view!='work' or key not in ('done','cancelled')],'priority':Task.PRIORITY_CHOICES},'counts': counts, 'attention_count': counts['attention'], 'due_counts': due_counts,
            'unread': notices.filter(read_at__isnull=True).count(), 'pending_reports': events.count(),
            'reports': auto_reports, 'notices': [{'id': newest.pk,'task':newest.task_id,'title':newest.text,'url':reverse('hr:task_detail',args=[newest.task_id])}] if newest else [],
            'view': view, 'due': due, 'query': query, 'items': payload, 'filter_errors': queue_filters.errors.get_json_data(),
            'pagination': {'page':page.number,'pages':page.paginator.num_pages,'total':page.paginator.count,'has_next':page.has_next(),'has_previous':page.has_previous()}}
