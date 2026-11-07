"""Deterministic workflow tasks. A unique source key prevents repeated assignments."""
from contextvars import ContextVar
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from accounts.permissions import has_permission
from crm.middleware import get_current_user
from .models import Task, TaskEvent, TaskNotice

quiet = ContextVar('task_automation_quiet', default=False)


def schedule_backfill():
    # A permissions form can change many overrides in one transaction.
    connection = transaction.get_connection()
    if not any(getattr(entry[1], '_workflow_backfill', False) for entry in connection.run_on_commit):
        def run():
            backfill()
        run._workflow_backfill = True
        transaction.on_commit(run)


def task_owner(task):
    return task.assigned_user or (task.assigned_to.user if task.assigned_to_id else None)


def choose_owner(preferred, permission):
    views = {'customers.case_edit':'customers.case', 'customers.registration_edit':'customers.registration',
             'customers.reception_refer':'customers.reception', 'customers.hiring_interview':'customers.hiring',
             'customers.followup':'customers.info', 'calls.edit':'calls.view', 'invoices.edit':'invoices.view'}
    def eligible(user):
        return user and user.is_active and has_permission(user, 'hr.view_tasks') and has_permission(user, permission) and (permission not in views or has_permission(user, views[permission]))
    for user in preferred:
        if eligible(user):
            return user
    candidates = [user for user in User.objects.filter(is_active=True).prefetch_related('groups', 'permission_overrides').order_by('-is_superuser', 'pk') if eligible(user)]
    from customers.access import is_card_manager
    managers = [user for user in candidates if is_card_manager(user)]
    return next(iter(managers or ([] if permission.startswith(('customers.', 'calls.')) and permission != 'customers.reception_refer' else candidates)), None)


def actor_or(user=None):
    actor = get_current_user()
    return actor if actor and actor.is_authenticated else user


def sync(key, kind, obj, title, owner, state, customer=None, date=None, time=None, description=None, allow_unassigned=False):
    with transaction.atomic():
        task = Task.objects.select_for_update().filter(source_key=key).first()
        if task and task.status == 'done' and state == 'cancelled':
            return task
        if not task and (state in ('done', 'cancelled') or not owner and not allow_unassigned):
            return None
        default_help = {'followup':'پیگیری مشتری را انجام دهید و نتیجه تماس را در مرکز مشتریان ثبت کنید.', 'case':'اطلاعات و مدارک مشتری را در تب پرونده تکمیل و ثبت اطلاعات کنید.', 'registration':'اطلاعات مرحله نهایی مشتری را در تب ثبت اطلاعات تکمیل و ذخیره کنید.', 'interview':'جلسه مصاحبه و ارزیابی کارجو را در تب استخدام ثبت کنید.', 'call':'تماس را پیگیری و نتیجه را در بخش تماس‌ها ثبت کنید.', 'invoice':'فاکتور را بررسی و صادر کنید؛ دریافت وجه را با وضعیت پرداخت‌شده در همان فاکتور ثبت کنید.', 'leave':'درخواست مرخصی را بررسی و نتیجه تأیید یا رد را ثبت کنید.'}
        description = description or default_help.get(kind,'وظیفه را در بخش مربوط انجام دهید.')
        values = dict(description=description, title=title[:200], assigned_user=owner, source_type=kind, source_id=obj.pk,
                      source_customer=customer, status=state if owner or allow_unassigned else 'cancelled', due_date=date, due_time=time)
        if task:
            if all(getattr(task, name) == value for name, value in values.items()):
                return task
            for name, value in values.items():
                setattr(task, name, value)
            task.save()
        else:
            task, _ = Task.objects.get_or_create(source_key=key, defaults={**values, 'created_by': actor_or()})
        return task


def sync_followup(item):
    customer = item.customer
    if customer.is_interviewer:
        Task.objects.filter(source_key='followup:'+str(item.pk)).exclude(status__in=['done','cancelled']).update(status='cancelled')
        return
    from customers.access import is_card_manager
    owner = choose_owner([customer.assigned_to, item.created_by if is_card_manager(item.created_by) else None], 'customers.followup')
    state = 'cancelled' if customer.is_deleted else 'done' if item.is_done else 'follow_up'
    if not item.is_done:
        sync_customer_flag(customer)
    for call in customer.calls.filter(follow_up_date=item.due_date):
        sync_call(call)
    return sync('followup:'+str(item.pk), 'followup', item, 'پیگیری مشتری — '+customer.name, owner, state, customer, item.due_date, item.due_time, description=(item.note + ('\nنتیجه ثبت‌شده: '+item.done_note if item.is_done and item.done_note else '')).strip() or None)


def sync_customer_flag(customer):
    """Older databases can contain a followup flag without a dated FollowUp."""
    key = 'customer-followup:'+str(customer.pk)
    existing = Task.objects.filter(source_key=key).first()
    if customer.is_interviewer:
        if existing and existing.status not in ('done','cancelled'):
            existing.status='cancelled';existing.save()
        return
    if customer.followups.filter(is_done=False).exists() or customer.calls.filter(status='followup', is_followed_up=False).exists():
        if existing and existing.status not in ('done','cancelled'):
            existing.status='cancelled';existing.save()
        return
    if not customer.needs_followup and not existing:
        return
    owner = choose_owner([customer.assigned_to], 'customers.followup')
    sync(key, 'customer_followup', customer, 'پیگیری مشتری بدون موعد — '+customer.name, owner,
         'cancelled' if customer.is_deleted else 'follow_up' if customer.needs_followup else 'done', customer,
         description='این مشتری نیاز به پیگیری دارد اما موعدی ثبت نشده است. تماس را ثبت و نیاز به پیگیری یا موعد بعدی را مشخص کنید.')


def sync_reception(rec):
    from .admission_tasks import reconcile, automatic_receiver
    reconcile(rec.customer)
    if (rec.customer.is_interviewer and rec.person_type != 'interviewer') or rec.workflow_version != 2:
        for task in Task.objects.filter(source_id=rec.pk, source_type__in=['reception','case','registration']).exclude(status__in=['done','cancelled']):
            task.status='cancelled';task.save()
        return
    customer = rec.customer
    preferred = [customer.assigned_to, rec.created_by, rec.referred_by] if not rec.referred_at and automatic_receiver(customer.assigned_to) else [rec.created_by, rec.referred_by, customer.assigned_to]
    owner = choose_owner(preferred, 'customers.reception_refer')
    sync('reception:'+str(rec.pk), 'reception', rec, 'ارجاع مراجعه‌کننده — '+customer.name, owner,
         'cancelled' if customer.is_deleted else 'done' if rec.referred_at else 'pending', customer,
         description='ورود ثبت شده است؛ مسئول مرحله بعد را در تب پذیرش انتخاب و فرد را به پرونده یا استخدام ارجاع دهید.')
    if not rec.referred_at:
        return
    if rec.person_type == 'interviewer':
        from customers.models import HiringApplication
        app = HiringApplication.objects.filter(reception=rec).first()
        if app:
            sync_hiring(app)
        return
    owner = choose_owner([customer.assigned_to, rec.referred_to], 'customers.case_edit')
    cancel = customer.is_deleted
    working = rec.work_sessions.exists()
    sync('case:'+str(rec.pk), 'case', rec, 'تکمیل پرونده — '+customer.name, owner,
         'cancelled' if cancel else 'done' if rec.case_completed_at else 'in_progress' if working else 'pending', customer)
    if rec.case_completed_at:
        owner = choose_owner([customer.assigned_to, rec.case_completed_by, rec.referred_to], 'customers.registration_edit')
        sync('registration:'+str(rec.pk), 'registration', rec, 'ثبت اطلاعات — '+customer.name, owner,
             'cancelled' if cancel else 'done' if rec.registration_completed_at else 'pending', customer)


def sync_hiring(app):
    from customers.models import InterviewSession
    rec = app.reception
    customer = rec.customer
    from .admission_tasks import reconcile
    reconcile(customer)
    active = bool(rec.referred_at or rec.workflow_version == 1)
    owner = choose_owner([customer.assigned_to, rec.referred_to], 'customers.hiring_interview')
    session = InterviewSession.objects.filter(application=app, kind='first').order_by('pk').first()
    state = 'done' if session and session.saved_at else 'in_progress' if session and session.started_at else 'pending'
    sync('interview:'+str(app.pk), 'interview', app, 'مصاحبه اول — '+customer.name, owner,
         'cancelled' if customer.is_deleted or not active else state, customer)
    from customers.recruitment_tasks import sync_interview_task
    for item in app.sessions.all():
        sync_interview_task(item, actor_or())
        sync_invitation(item)


def sync_invitation(session):
    rec = session.application.reception
    owner = choose_owner([rec.customer.assigned_to, rec.referred_to], 'customers.hiring_interview')
    state = 'cancelled' if rec.customer.is_deleted or not (rec.referred_at or rec.workflow_version == 1) or not session.saved_at or not session.invite else 'done' if session.will_attend == 'no' or session.collaboration else 'follow_up'
    when = timezone.localtime(session.invitation_at) if session.invitation_at else None
    sync('invitation:'+str(session.pk), 'invitation', session, 'پیگیری دعوت به همکاری — '+rec.customer.name, owner,
         state, rec.customer, when.date() if when else None, when.time().replace(tzinfo=None) if when else None,
         description='نتیجه حضور و تبدیل به همکار را در همان جلسه استخدام ثبت کنید.')


def sync_call(call):
    # A FollowUp is authoritative when both representations describe one appointment.
    if call.customer_id and call.customer.followups.filter(due_date=call.follow_up_date).exists():
        for task in Task.objects.filter(source_key='call:'+str(call.pk)).exclude(status__in=['done','cancelled']):
            task.status='cancelled'; task.save()
        return
    owner = choose_owner([call.customer.assigned_to if call.customer_id else None, call.called_by, call.created_by], 'calls.edit')
    state = 'done' if call.is_followed_up else 'follow_up' if call.status == 'followup' else 'cancelled'
    if call.customer_id and state == 'follow_up':
        sync_customer_flag(call.customer)
    if call.customer_id and (call.customer.is_deleted or call.customer.is_interviewer):
        state = 'cancelled'
    sync('call:'+str(call.pk), 'call', call, 'پیگیری تماس — '+call.caller_name, owner, state, customer=call.customer, date=call.follow_up_date, time=call.follow_up_time)


def sync_invoice(invoice):
    owner = choose_owner([invoice.created_by, invoice.customer.assigned_to], 'invoices.edit')
    state = {'draft': 'pending', 'issued': 'follow_up', 'paid': 'done', 'cancelled': 'cancelled'}[invoice.status]
    sync('invoice:'+str(invoice.pk), 'invoice', invoice, 'رسیدگی فاکتور — '+invoice.number, owner,
         'cancelled' if invoice.customer.is_deleted or invoice.customer.is_interviewer else state, invoice.customer, invoice.due_date)


def sync_leave(leave):
    owner = choose_owner([leave.reviewed_by], 'hr.review_leaves')
    sync('leave:'+str(leave.pk), 'leave', leave, 'بررسی مرخصی — '+leave.employee.full_name, owner,
         'pending' if leave.status == 'pending' else 'done', date=leave.start_date)


def record_change(task, before=None):
    owner = task_owner(task)
    previous_owner = task_owner(before) if before else None
    actor = actor_or()
    assignment = bool(owner and (not before or owner.pk != getattr(previous_owner, 'pk', None) or before.status in ('done','cancelled') and task.status not in ('done','cancelled')))
    if assignment:
        TaskNotice.objects.filter(task=task, read_at__isnull=True).exclude(user=owner).update(read_at=timezone.now())
        if task.status not in ('done', 'cancelled'):
            TaskNotice.objects.create(task=task, user=owner, text=('وظیفه جدید: '+task.title)[:250])
    if before and before.status != task.status:
        report_user = actor or owner
        required = bool(not quiet.get() and report_user and task.status in ('done', 'follow_up') and before.status not in ('done', 'cancelled'))
        event = TaskEvent.objects.create(snapshot={'title':task.title,'description':task.description or ''}, task=task, from_status=before.status, to_status=task.status, actor=actor, report_user=report_user, report_required=required)
        if owner and not quiet.get() and not assignment:
            TaskNotice.objects.create(task=task, user=owner, text=('وضعیت «'+task.title+'»: '+task.get_status_display())[:250])
        if required and report_user.pk != getattr(owner, 'pk', None):
            TaskNotice.objects.create(task=task, user=report_user, text=('گزارش کار انجام‌شده: '+task.title)[:250])
    if task.status == 'cancelled':
        TaskNotice.objects.filter(task=task, read_at__isnull=True).update(read_at=timezone.now())


def backfill():
    from customers.models import Customer, FollowUp, Reception, HiringApplication
    from calls.models import Call
    from sales.models import Invoice
    from .models import LeaveRequest
    token = quiet.set(True)
    try:
        from .admission_tasks import reconcile, backfill_assignments
        backfill_assignments()
        for item in FollowUp.objects.filter(is_done=False, customer__is_deleted=False).select_related('customer__assigned_to', 'created_by').iterator():
            sync_followup(item)
        for item in Reception.objects.filter(workflow_version=2, registration_completed_at__isnull=True, customer__is_deleted=False).select_related('customer__assigned_to').iterator():
            sync_reception(item)
        for item in HiringApplication.objects.select_related('reception__customer__assigned_to').iterator():
            sync_hiring(item)
        for item in Customer.objects.filter(needs_followup=True,is_deleted=False).iterator():
            sync_customer_flag(item)
        for item in Call.objects.filter(status='followup', is_followed_up=False).iterator():
            sync_call(item)
        for item in Invoice.objects.filter(status__in=['draft', 'issued'], customer__is_deleted=False).iterator():
            sync_invoice(item)
        for item in LeaveRequest.objects.filter(status='pending').iterator():
            sync_leave(item)
        # Reconcile tasks whose sources were completed, deleted or changed with bulk updates.
        sources = {'admission':(Customer.all_objects,reconcile), 'followup':(FollowUp,sync_followup), 'customer_followup':(Customer.all_objects,sync_customer_flag),
                   'reception':(Reception,sync_reception), 'case':(Reception,sync_reception),
                   'registration':(Reception,sync_reception), 'interview':(HiringApplication,sync_hiring),
                   'call':(Call,sync_call), 'invoice':(Invoice,sync_invoice), 'leave':(LeaveRequest,sync_leave)}
        from customers.models import InterviewSession
        sources['invitation'] = (InterviewSession,sync_invitation)
        for task in Task.objects.exclude(status__in=['done','cancelled']).exclude(source_type='').iterator():
            source = sources.get(task.source_type)
            if not source:
                continue
            model, handler = source
            records = model.objects if hasattr(model,'objects') else model
            item = records.filter(pk=task.source_id).first()
            if item:
                handler(item)
            else:
                task.status='cancelled';task.save()
        for task in Task.objects.exclude(status__in=['done', 'cancelled']).select_related('assigned_user', 'assigned_to__user').iterator():
            owner = task_owner(task)
            if owner and not TaskNotice.objects.filter(task=task, user=owner).exists():
                TaskNotice.objects.create(task=task, user=owner, text=('وظیفه فعال شما: '+task.title)[:250])
    finally:
        quiet.reset(token)
