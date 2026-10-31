"""Admission -> referral -> case -> profile, with server-side stage/permission gates."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Prefetch, OuterRef, Subquery, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.permissions import get_user_permissions, has_permission, require_permission
from .access import can_edit_card, is_card_manager
from .forms import CustomerCaseForm, CustomerForm
from .models import Customer, CustomerCase, Reception, RecordUpdate
from calls.models import Call
from crm.duplicate_check import normalize_digits

TAB_PERMISSIONS = {
    'info': 'customers.info', 'reception': 'customers.reception',
    'case': 'customers.case', 'registration': 'customers.registration',
    'hiring': 'customers.hiring',
    'invoice': 'customers.invoices',
}


def allowed_tabs(user):
    permissions = get_user_permissions(user)
    return [tab for tab, permission in TAB_PERMISSIONS.items() if permission in permissions]


def workflow_records():
    return Reception.objects.filter(workflow_version=2, customer__is_deleted=False).select_related(
        'customer', 'customer__assigned_to', 'customer__ad_source', 'customer__case', 'customer__case__product',
        'referred_to', 'referred_by', 'created_by', 'case_completed_by', 'registration_completed_by',
    ).prefetch_related(Prefetch(
        'customer__calls',
        queryset=Call.objects.select_related('called_by').order_by('-call_date', '-pk')[:1],
        to_attr='latest_contact',
    ))


def editable_records(user):
    records = workflow_records()
    if not is_card_manager(user):
        records = records.filter(customer__assigned_to=user)
    return records


def attach_updates(request, page, scope):
    if not has_permission(request.user, 'customers.history'):
        return
    records = list(page.object_list)
    updates = {}
    for item in RecordUpdate.objects.filter(scope=scope, customer_id__in=[r.customer_id for r in records]).select_related('edited_by').order_by('-created_at'):
        updates.setdefault(item.customer_id, []).append(item)
    for rec in records:
        rec.updates = updates.get(rec.customer_id, [])
    page.object_list = records


def hiring_records(user):
    """One row per interview visitor, including the preserved earlier versions."""
    latest = Reception.objects.filter(
        customer_id=OuterRef('customer_id'), person_type='interviewer',
    ).order_by('-created_at', '-pk').values('pk')[:1]
    # Hiring also includes archived records; the same owner boundary applies.
    records = Reception.objects.filter(
        customer__is_deleted=False, person_type='interviewer', pk=Subquery(latest),
    ).select_related('customer', 'customer__assigned_to', 'customer__ad_source',
                     'customer__case', 'customer__case__product', 'created_by',
                     'referred_to', 'referred_by', 'case_completed_by', 'registration_completed_by')
    records = records.prefetch_related(Prefetch(
        'customer__calls', queryset=Call.objects.select_related('called_by').order_by('-call_date', '-pk')[:1],
        to_attr='latest_contact',
    ))
    if not is_card_manager(user):
        records = records.filter(customer__assigned_to=user)
    return records.order_by('-created_at', '-pk')


def referral_users(person_type='customer'):
    # Honor effective per-user overrides, including explicit denials.
    users = User.objects.filter(is_active=True).prefetch_related('groups', 'permission_overrides').order_by('first_name', 'username')
    permission = 'customers.hiring' if person_type == 'interviewer' else 'customers.case'
    return [user for user in users if has_permission(user, permission) and (person_type == 'interviewer' or has_permission(user, 'customers.case_edit'))]


def search_records(records, query):
    if query:
        records = records.filter(Q(customer__name__icontains=query) |
                                 Q(customer__mobile__icontains=normalize_digits(query)))
    return records


def selected_record(request, records):
    value = request.GET.get('r', '')
    if value.isdigit():
        return records.filter(pk=int(value)).first()
    customer_id = request.GET.get('c', '')
    if customer_id.isdigit():
        return records.filter(customer_id=int(customer_id)).first()
    return None


def case_initial(customer, case):
    condition = (customer.calls.exclude(requested_condition='').order_by('-created_at', '-pk')
                 .values_list('requested_condition', flat=True).first())
    initial = {}
    if condition and not (case and case.condition):
        initial['condition'] = condition
    if condition == 'retired' and not (case and case.job):
        initial['job'] = 'retired'
    return initial


def build_workflow_context(request):
    tabs = allowed_tabs(request.user)
    labels = {'info': ('👥', 'اطلاعات'), 'reception': ('🤝', 'پذیرش'), 'case': ('📁', 'پرونده'),
              'registration': ('📝', 'ثبت اطلاعات'), 'hiring': ('🧑‍💼', 'استخدام'), 'invoice': ('📄', 'فاکتورها')}
    query = request.GET.get('workflow_q', '').strip()[:200]
    active = getattr(request, '_hub_tab', request.GET.get('tab', 'info'))
    def paginated(records, tab, page_key):
        return Paginator(search_records(records, query if active == tab else ''), 30).get_page(request.GET.get(page_key))
    context = {'allowed_hub_tabs': tabs, 'registration_unlocked': False, 'workflow_query': query,
               'hub_tab_items': [{'key': tab, 'icon': labels[tab][0], 'label': labels[tab][1]} for tab in tabs]}
    visible = editable_records(request.user)
    if 'registration' in tabs:
        ready = visible.filter(person_type='customer', case_completed_at__isnull=False).order_by('-case_completed_at', '-pk')
        context.update(registration_unlocked=ready.exists(), registration_choices=ready, registration_records=paginated(ready, 'registration', 'registration_page'),
                       registration_record=selected_record(request, ready))
    if 'reception' in tabs:
        records = workflow_records().order_by('-wait_started_at', '-pk')
        context.update(reception_customers=Customer.objects.order_by('name'),
                       reception_records=paginated(records, 'reception', 'reception_page'), referral_users=referral_users() if active == 'reception' else [], hiring_referral_users=referral_users('interviewer') if active == 'reception' else [],
                       legacy_receptions=Reception.objects.filter(workflow_version=1, customer__is_deleted=False)
                       .select_related('customer', 'created_by').order_by('-created_at')[:100])
    if 'case' in tabs:
        records = visible.filter(person_type='customer', referred_at__isnull=False).order_by('-referred_at', '-pk')
        rec = selected_record(request, records)
        case = getattr(rec.customer, 'case', None) if rec else None
        form = None
        if rec:
            form = CustomerCaseForm(instance=case, initial=case_initial(rec.customer, case))
        bound = getattr(request, '_workflow_bound_form', None)
        if bound is not None:
            form = bound
        legacy_cases = CustomerCase.objects.filter(customer__is_deleted=False, customer__receptions__workflow_version=1)
        if not is_card_manager(request.user):
            legacy_cases = legacy_cases.filter(customer__assigned_to=request.user)
        context.update(case_choices=records, case_records=paginated(records, 'case', 'case_page'), case_record=rec,
                       case_customer=rec.customer if rec else None, customer_case=case,
                       case_form=form,
                       legacy_cases=legacy_cases.distinct().select_related('customer', 'product').order_by('-updated_at')[:100])
    if 'hiring' in tabs:
        context['hiring_records'] = paginated(hiring_records(request.user), 'hiring', 'hiring_page')
    for item in context['hub_tab_items']:
        records = context.get(item['key'] + '_records')
        if records is not None:
            item['count'] = records.paginator.count
    for name, scope in (('reception_records', 'reception'), ('case_records', 'case')):
        if name in context and active == name.removesuffix('_records'):
            attach_updates(request, context[name], scope)
    return context


def posted_pk(request, key):
    value = request.POST.get(key, '')
    return int(value) if value.isascii() and value.isdigit() and len(value) < 16 else 0


def back_to(tab, rec=None):
    url = f"{reverse('customers:hub')}?tab={tab}"
    return f'{url}&r={rec.pk}' if rec else url


def admission_destination(user, rec):
    tab = 'hiring' if rec.person_type == 'interviewer' and has_permission(user, 'customers.hiring') else 'reception'
    return back_to(tab, rec)


def record_change(rec, user, changes):
    RecordUpdate.objects.create(customer=rec.customer, scope='reception', changes=changes, edited_by=user)


@login_required
@require_permission('customers.reception')
@require_POST
@transaction.atomic
def reception_action(request):
    action = request.POST.get('action', '')
    if action in ('answer', 'arrive'):
        if not has_permission(request.user, 'customers.reception_add'):
            raise PermissionDenied('مجوز ثبت ورود ندارید.')
        person = request.POST.get('person_type', '')
        if person not in dict(Reception.PERSON_CHOICES):
            return HttpResponse('نوع مراجعه‌کننده را انتخاب کنید.', status=400)
        customer = get_object_or_404(Customer.objects.select_for_update(), pk=posted_pk(request, 'customer'))
        current = Reception.objects.filter(customer=customer, workflow_version=2,
                                           registration_completed_at__isnull=True).first()
        if current:
            messages.info(request, 'این فرد یک مراجعه در جریان دارد؛ زمان ورود قبلی حفظ شد.')
            return redirect(admission_destination(request.user, current))
        now = timezone.now()
        rec = Reception.objects.create(customer=customer, person_type=person, wait_started_at=now,
                                       is_waiting=True, created_by=request.user)
        customer.is_interviewer = person == 'interviewer'
        customer.save(update_fields=['is_interviewer', 'updated_at'])
        messages.success(request, 'ورود ثبت شد؛ شمارش انتظار از زمان سیستم شروع شد.')
        return redirect(admission_destination(request.user, rec))

    if action != 'refer':
        return HttpResponse('عملیات پذیرش معتبر نیست.', status=400)
    if not has_permission(request.user, 'customers.reception_refer'):
        raise PermissionDenied('مجوز ارجاع پذیرش ندارید.')
    rec = get_object_or_404(Reception.objects.select_for_update(),
                           pk=posted_pk(request, 'reception'), workflow_version=2)
    customer = get_object_or_404(Customer.objects.select_for_update(), pk=rec.customer_id)
    if rec.referred_at or not rec.is_waiting:
        messages.info(request, 'این مراجعه قبلاً ارجاع شده است؛ زمان و مسئول قبلی حفظ شدند.')
        return redirect(back_to('reception', rec))
    target = get_object_or_404(User.objects, pk=posted_pk(request, 'user'), is_active=True)
    permission = 'customers.hiring' if rec.person_type == 'interviewer' else 'customers.case'
    if not has_permission(target, permission) or (rec.person_type == 'customer' and not has_permission(target, 'customers.case_edit')):
        return HttpResponse('کاربر انتخاب‌شده دسترسی مرحله بعد این مراجعه را ندارد.', status=400)
    now = timezone.now()
    rec.referred_to, rec.referred_by, rec.referred_at = target, request.user, now
    rec.wait_ended_at, rec.is_waiting = now, False
    rec.wait_minutes_total = rec.wait_seconds // 60
    rec.save()
    customer.assigned_to = target
    customer.save(update_fields=['assigned_to', 'updated_at'])
    record_change(rec, request.user, [{'label': 'ارجاع پذیرش', 'old': 'در انتظار',
                                     'new': target.get_full_name() or target.username}])
    destination = 'استخدام' if rec.person_type == 'interviewer' else 'پرونده'
    messages.success(request, f'ارجاع ثبت و تایمر متوقف شد؛ فرد در تب {destination} کاربر مسئول قرار گرفت.')
    return redirect(admission_destination(request.user, rec))


@login_required
@require_permission('customers.reception')
@require_GET
def reception_clock(request):
    """Only timing/state fields, never customer details; used for multi-user timer sync."""
    rows = workflow_records().filter(is_waiting=True, wait_started_at__isnull=False).values('pk', 'wait_started_at')
    return JsonResponse({'server_now': timezone.now().isoformat(), 'waiting': list(rows)},
                        headers={'Cache-Control': 'no-store'})


@login_required
@require_permission('customers.hiring')
@require_GET
def hiring_clock(request):
    rows = hiring_records(request.user).filter(workflow_version=2, is_waiting=True,
                                              wait_started_at__isnull=False).values('pk', 'wait_started_at')
    return JsonResponse({'server_now': timezone.now().isoformat(), 'waiting': list(rows)},
                        headers={'Cache-Control': 'no-store'})


def case_snapshot(case):
    if not case:
        return {}
    values = {key: str(getattr(case, key) or '') for key in CustomerCaseForm.Meta.fields}
    for key in ('condition', 'cheque_owner', 'job', 'visit_result'):
        values[key] = getattr(case, f'get_{key}_display')()
    return values


@login_required
@require_permission('customers.case')
@require_permission('customers.case_edit')
@require_POST
@transaction.atomic
def case_save(request):
    rec = get_object_or_404(Reception.objects.select_for_update(),
                           pk=posted_pk(request, 'reception'), workflow_version=2)
    customer = get_object_or_404(Customer.objects.select_for_update(), pk=rec.customer_id)
    if not can_edit_card(request.user, customer):
        raise PermissionDenied('پرونده فقط برای مسئول کارت، سرپرست و ادمین قابل تکمیل است.')
    if rec.person_type != 'customer':
        return HttpResponse('این مراجعه در مسیر استخدام قرار دارد.', status=409)
    if not rec.referred_at:
        return HttpResponse('ابتدا مراجعه‌کننده را از پذیرش ارجاع دهید.', status=409)
    case = CustomerCase.objects.filter(customer=customer).first()
    before = case_snapshot(case)
    form = CustomerCaseForm(request.POST, instance=case)
    if form.is_valid():
        case = form.save(commit=False)
        case.customer = customer
        if not case.created_by_id:
            case.created_by = request.user
        case.save()
        if not rec.case_completed_at:
            rec.case_completed_at, rec.case_completed_by = timezone.now(), request.user
            rec.save(update_fields=['case_completed_at', 'case_completed_by', 'updated_at'])
        from .hub_views import _log_record_update, CASE_LABELS
        after = case_snapshot(case)
        _log_record_update(customer, 'case', before, after, CASE_LABELS, request.user)
        messages.success(request, 'پرونده ذخیره شد؛ مرحله ثبت اطلاعات برای این فرد فعال است.')
        return redirect(back_to('case', rec))
    # Render submitted values and errors; no partial writes and no lost input.
    from .hub_views import customer_hub
    request.GET = request.GET.copy()
    request.GET.update({'tab': 'case', 'r': str(rec.pk)})
    request._workflow_bound_form = form
    response = customer_hub(request)
    response.status_code = 400
    return response


@login_required
@require_permission('customers.registration')
@require_permission('customers.registration_edit')
@transaction.atomic
def registration_form(request, pk):
    if request.method not in ('GET', 'POST'):
        return HttpResponse(status=405, headers={'Allow': 'GET, POST'})
    rec = get_object_or_404(Reception.objects.select_for_update(), pk=pk, workflow_version=2)
    customer = get_object_or_404(Customer.objects.select_for_update(), pk=rec.customer_id)
    if not can_edit_card(request.user, customer):
        raise PermissionDenied('ثبت اطلاعات فقط برای مسئول کارت، سرپرست و ادمین مجاز است.')
    if rec.person_type != 'customer':
        return HttpResponse('اطلاعات این فرد در تب استخدام نمایش داده می‌شود.', status=409)
    if not rec.referred_at or not rec.case_completed_at:
        return HttpResponse('ابتدا ارجاع و ثبت پرونده را تکمیل کنید.', status=409)
    # Same profile popup, fully prefilled. The tab permission authorizes this stage.
    form = CustomerForm(request.POST if request.method == 'POST' else None, instance=customer, limited=not has_permission(request.user, 'customers.profile_full'))
    form.fields.pop('assigned_to', None)  # Changing ownership is a separate operation.
    if request.method == 'POST' and form.is_valid():
        form.save()
        if not rec.registration_completed_at:
            rec.registration_completed_at, rec.registration_completed_by = timezone.now(), request.user
            rec.info_submitted = True
            rec.save(update_fields=['registration_completed_at', 'registration_completed_by', 'info_submitted', 'updated_at'])
        messages.success(request, 'اطلاعات مراجعه‌کننده با موفقیت ثبت شد.')
        if request.headers.get('HX-Request'):
            return HttpResponse(status=204, headers={'HX-Redirect': back_to('registration', rec), 'HX-Trigger': 'closeModal'})
        return redirect(back_to('registration', rec))
    return render(request, 'customers/form_modal.html', {
        'form': form, 'customer': customer, 'title': f'ثبت اطلاعات — {customer.name}',
        'submit_label': 'ثبت اطلاعات', 'form_action': reverse('customers:registration_form', args=[rec.pk]),
    })
