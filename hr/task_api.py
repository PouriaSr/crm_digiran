from django import forms
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache
from accounts.permissions import require_permission, has_permission
from .models import Task, TaskEvent, TaskNotice, TaskReport
from .task_access import visible_tasks, owned_tasks, source_url


class ReportForm(forms.Form):
    text = forms.CharField(label='گزارش انجام کار', min_length=3, max_length=4000, strip=True)


@require_permission('hr.view_tasks')
@require_GET
@never_cache
def inbox(request):
    from .task_inbox import personal_inbox
    return JsonResponse(personal_inbox(request.user, request.GET))


@require_permission('hr.view_tasks')
@require_POST
def mark_read(request):
    if request.POST.get('scope') == 'all':
        count = TaskNotice.objects.filter(user=request.user, task__in=visible_tasks(request.user), read_at__isnull=True).update(read_at=timezone.now())
        return JsonResponse({'ok': True, 'count': count})
    raw = request.POST.get('notice', '')
    if not raw.isascii() or not raw.isdigit() or len(raw) > 16:
        return JsonResponse({'error': 'اعلان معتبر نیست.'}, status=400)
    notice = get_object_or_404(TaskNotice, pk=raw, user=request.user, task__in=visible_tasks(request.user))
    TaskNotice.objects.filter(task=notice.task,user=request.user,read_at__isnull=True).update(read_at=timezone.now())
    return JsonResponse({'ok': True})


@require_permission('hr.view_tasks')
@require_permission('hr.report_tasks')
@require_POST
@transaction.atomic
def submit_report(request, pk):
    get_object_or_404(visible_tasks(request.user), pk=pk)
    task = get_object_or_404(Task.objects.select_for_update(), pk=pk)
    form = ReportForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': form.errors.get_json_data()}, status=400)
    raw = request.POST.get('event', '')
    if raw:
        if not raw.isascii() or not raw.isdigit() or len(raw) > 16:
            return JsonResponse({'error': 'درخواست گزارش معتبر نیست.'}, status=400)
        event = get_object_or_404(TaskEvent.objects.select_for_update(), pk=raw, task=task, report_user=request.user, report_required=True)
    else:
        # A manual assignment has no external source to complete it.
        if task.source_type or task.hiring_session_id or not owned_tasks(request.user).filter(pk=pk).exists():
            return JsonResponse({'error': 'ابتدا کار مرتبط را در بخش مربوط انجام دهید.'}, status=409)
        if task.status == 'cancelled':
            return JsonResponse({'error': 'این وظیفه لغو شده است.'}, status=409)
        event = task.events.filter(to_status='done', report_user=request.user, report_required=True).first() if task.status == 'done' else None
        if not event:
            if task.status == 'done':
                return JsonResponse({'error': 'این وظیفه قبلاً تمام شده است.'}, status=409)
            task.status = 'done'
            task.save()
            event = task.events.filter(to_status='done', report_user=request.user, report_required=True).first()
    report, created = TaskReport.objects.get_or_create(event=event, defaults={'author': request.user, 'text': form.cleaned_data['text']})
    TaskNotice.objects.filter(task=task, user=request.user, read_at__isnull=True).update(read_at=timezone.now())
    return JsonResponse({'ok': True, 'already_saved': not created, 'status': task.get_status_display(), 'report': report.pk, 'task':task.pk, 'message': ('گزارش ثبت شد؛ وضعیت وظیفه «'+task.get_status_display()+'» است.') if created else 'این گزارش قبلاً ثبت شده است؛ ثبت تکراری انجام نشد.'})
