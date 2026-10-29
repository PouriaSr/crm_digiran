from accounts.permissions import require_roles, ROLE_ADMIN, ROLE_SALES_MANAGER
import jdatetime
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.core.exceptions import PermissionDenied
from .access import can_edit_card, can_edit_call, is_card_manager
from .scheduling import parse_followup_time
from django.db.models import Q, Sum, Count, OuterRef, Subquery, IntegerField
from django.db.models.functions import Coalesce
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_GET
from accounts.permissions import has_permission, require_permission
from .models import Customer, FollowUp
from .sms import send_address_sms
from .forms import HubCallForm
from calls.models import Call
from sales.models import Invoice
from ads.models import AdSource

def parse_jalali(value):
    """«۱۴۰۵/۰۸/۰۳» یا «1405/08/03» → date (یا None)"""
    import jdatetime
    value = (value or '').strip()
    if not value:
        return None
    fa = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
    value = value.translate(fa).replace('-', '/')
    parts = [p for p in value.split('/') if p.strip()]
    if len(parts) != 3:
        return None
    try:
        y, m, d = (int(p) for p in parts)
        return jdatetime.date(y, m, d).togregorian()
    except Exception:
        return None


def _followup_annotation():
    """زیرکوئری تاریخ پیگیری باز / آخرین پیگیری انجام‌شده"""
    open_due = Subquery(
        FollowUp.objects.filter(customer=OuterRef('pk'), is_done=False)
        .order_by('due_date', 'due_time', 'pk').values('due_date')[:1]
    )
    last_done = Subquery(
        FollowUp.objects.filter(customer=OuterRef('pk'), is_done=True)
        .order_by('-done_at', '-id').values('due_date')[:1]
    )
    return open_due, last_done


def _quick_call_redirect(request, default_back):
    """بازگشت به همان صفحه‌ای که مودال از آن باز شد (فقط مسیرهای امن داخلی)"""
    nxt = (request.POST.get('next') or '').strip()
    if nxt.startswith(reverse('customers:hub').split('/customers/')[0] + '/customers/') and '//' not in nxt:
        return redirect(nxt)
    return redirect(default_back)


def _close_open_followups(customer, note=''):
    """بستن پیگیری‌های باز با ثبت نتیجه"""
    from django.utils import timezone as _tz
    now = _tz.now()
    n = 0
    for fu in FollowUp.objects.filter(customer=customer, is_done=False):
        fu.is_done = True
        fu.done_at = now
        fu.done_note = note
        fu.save(update_fields=['is_done', 'done_at', 'done_note'])
        n += 1
    return n


def _sync_needs_followup(customer):
    """همگام‌سازی پرچم مشتری با وجود پیگیری باز"""
    has_open = FollowUp.objects.filter(customer=customer, is_done=False).exists()
    if customer.needs_followup != has_open:
        customer.needs_followup = has_open
        customer.save(update_fields=['needs_followup', 'updated_at'])
    return has_open


RECEPTION_LABELS = {
    'person_type': 'فرد مورد نظر',
    'has_visit': 'مراجعه حضوری',
    'wait_choice': 'مدت انتظار',
    'info_submitted': 'ثبت اطلاعات',
}

CASE_LABELS = {
    'condition': 'شرایط',
    'cheque_owner': 'مالک چک',
    'cheque_other_name': 'نام صاحب چک',
    'cheque_other_phone': 'شماره صاحب چک',
    'job': 'شغل',
    'credit_rank': 'رتبه اعتباری',
    'active_loans': 'وام‌های فعال',
    'product': 'کالا',
    'quantity': 'تعداد',
    'visit_result': 'نتیجه مراجعه',
}


def _display(value):
    """نمایش خوانا برای مقایسه/لاگ"""
    if value is None or value == '':
        return '—'
    if isinstance(value, bool):
        return 'بله' if value else 'خیر'
    if isinstance(value, (list, tuple)):
        return '، '.join(str(v) for v in value) if value else '—'
    return str(value)


def _build_changes(old, new, labels):
    """فهرست تغییرات: [{'label','old','new'}]"""
    out = []
    for key, label in labels.items():
        if key not in old and key not in new:
            continue
        a, b = _display(old.get(key)), _display(new.get(key))
        if a != b:
            out.append({'label': label, 'old': a, 'new': b})
    return out


def _log_record_update(customer, scope, old, new, labels, user):
    from .models import RecordUpdate
    changes = _build_changes(old, new, labels)
    if not changes:
        return None
    return RecordUpdate.objects.create(
        customer=customer, scope=scope, changes=changes, edited_by=user,
    )


def _calls_count_subquery():
    """تعداد تماس‌های هر مشتری — با Subquery تا join به جدول customers نزند"""
    sq = (Call.objects
          .filter(customer=OuterRef('customer_id'))
          .values('customer')
          .annotate(n=Count('id'))
          .values('n'))
    return Coalesce(Subquery(sq, output_field=IntegerField()), 0)


@never_cache
@login_required
def customer_hub(request):
    from .reception_workflow import allowed_tabs, build_workflow_context
    tabs = allowed_tabs(request.user)
    if not tabs:
        raise PermissionDenied('دسترسی به تب‌های مرکز مشتریان ندارید.')
    tab = request.GET.get('tab') or tabs[0]
    tab = {'call': 'info', 'followup': 'info', 'visit': 'info', 'recruitment': 'registration'}.get(tab, tab)
    if tab not in tabs:
        raise PermissionDenied('دسترسی این تب برای شما فعال نیست.')
    search = request.GET.get('q', '').strip()
    
    from django.db.models import Prefetch
    open_due_sq, last_done_sq = _followup_annotation()
    customers = (Customer.all_objects
                 .select_related('assigned_to', 'created_by', 'ad_source')
                 .prefetch_related(Prefetch(
                     'calls',
                     queryset=Call.objects.select_related('called_by')
                                         .order_by('-call_date'),
                     to_attr='history_calls',
                 ))
                 .annotate(open_fu_due=open_due_sq, last_fu_done=last_done_sq)
                 .order_by('-created_at'))

    if search:
        customers = customers.filter(Q(name__icontains=search) | Q(mobile__icontains=search))

    today = timezone.localdate()
    from django.db.models import Case, When, Value, F, TimeField
    due_time_sq = Subquery(
        FollowUp.objects.filter(customer=OuterRef('pk'), is_done=False)
        .order_by('due_date', 'due_time', 'pk').values('due_time')[:1],
        output_field=TimeField(),
    )
    now_time = timezone.localtime().time().replace(tzinfo=None)
    customers = customers.annotate(open_fu_time=due_time_sq)
    overdue = Q(open_fu_due__lt=today) | (Q(open_fu_due=today) & Q(open_fu_time__lt=now_time))
    customers = customers.annotate(followup_priority=Case(
        When(overdue, then=Value(0)),
        When(open_fu_due=today, then=Value(1)),
        When(open_fu_due__gt=today, then=Value(2)),
        default=Value(3), output_field=IntegerField(),
    ))
    priority = request.GET.get('priority', '')
    if priority == 'overdue':
        customers = customers.filter(overdue)
    elif priority == 'today':
        customers = customers.filter(open_fu_due=today)
    elif priority == 'upcoming':
        customers = customers.filter(open_fu_due__gt=today)
    elif priority == 'none':
        customers = customers.filter(open_fu_due__isnull=True)
    date_field = request.GET.get('date_field', 'followup')
    field = 'created_at__date' if date_field == 'created' else 'open_fu_due'
    date_from, date_to = request.GET.get('date_from', ''), request.GET.get('date_to', '')
    start, end = parse_jalali(date_from), parse_jalali(date_to)
    if (date_from and not start) or (date_to and not end) or (start and end and start > end):
        messages.error(request, 'بازه تاریخ معتبر نیست؛ تاریخ شمسی شروع و پایان را بررسی کنید.')
        customers = customers.none()
    else:
        if start:
            customers = customers.filter(**{field + '__gte': start})
        if end:
            customers = customers.filter(**{field + '__lte': end})
    sort = request.GET.get('sort', 'priority')
    if sort == 'oldest':
        customers = customers.order_by('created_at', 'pk')
    elif sort == 'recent':
        customers = customers.order_by('-created_at', '-pk')
    else:
        sort = 'priority'
        customers = customers.order_by('followup_priority', F('open_fu_due').asc(nulls_last=True), F('open_fu_time').asc(nulls_first=True), '-created_at', '-pk')

    workflow_context = build_workflow_context(request)

    # گزینه‌های لیست‌ها
    filter_customers = (Customer.all_objects
                        .annotate(n_calls=Count('calls'))
                        .order_by('name', 'id')[:1000])
    filter_sources = AdSource.objects.order_by('phone_number')
    reassign_users = (User.objects.filter(is_active=True)
                      .order_by('first_name', 'username'))

    # ═══ پیگیری‌ها: یک تعریف واحد از «در انتظار» ═══
    # در انتظار = تیک نخورده + تاریخ دارد + تاریخش رسیده (امروز یا گذشته)
    open_followups = FollowUp.objects.filter(
        is_done=False, customer__is_deleted=False,
    )
    due_followups = open_followups.filter(due_date__lte=today)

    
    total_customers = Customer.objects.count()
    total_leads = Customer.objects.filter(stage='lead').count()
    pending_followups = due_followups.count()
    upcoming_followups_count = open_followups.filter(due_date__gt=today).count()
    recent_revenue = Invoice.objects.filter(status='paid').aggregate(total=Sum('total'))['total'] or 0

    context = {
        'active_tab': tab,
        'search': search,
        'table_filters': {'priority': priority, 'date_field': date_field, 'date_from': date_from, 'date_to': date_to, 'sort': sort},
        'stats': {
            'total_customers': total_customers,
            'total_leads': total_leads,
            'pending_followups': pending_followups,
            'recent_revenue': recent_revenue,
        },
        'customers': customers[:50],
        'today': today,
        'filter_customers': filter_customers,
        'filter_sources': filter_sources,
        'reassign_users': reassign_users,
        'contact_type_choices': Call.CONTACT_TYPE_CHOICES,
        'type_choices': Call.CALL_TYPE_CHOICES,
        'invoices': (Invoice.objects.select_related('customer', 'created_by').order_by('-created_at')[:20]) if 'invoice' in tabs else [],
        'call_form': HubCallForm(user=request.user),
    }
    
    context.update(workflow_context)

    # دکمه «ثبت تماس جدید»:
    #   جستجو خالی → غیرفعال · مشتری موجود → غیرفعال · مشتری ناموجود → فعال
    show_new = bool(search) and not Customer.all_objects.filter(
        Q(name__icontains=search) | Q(mobile__icontains=search)
    ).exists()
    context['show_new'] = show_new

    is_partial = (
        request.headers.get('HX-Request')
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.GET.get('partial') == '1'
    )
    if is_partial and tab == 'info':
        response = render(request, 'customers/hub_table_partial.html', context)
        response['X-Show-New-Customer'] = 'true' if show_new else 'false'
        return response
        
    return render(request, 'customers/hub.html', context)


@login_required
@require_permission('customers.add')
@require_POST
def hub_submit_call(request):
    back = f"{reverse('customers:hub')}?tab=call"
    form = HubCallForm(request.POST, user=request.user)
    if not form.is_valid():
        for field, errors in form.errors.items():
            label = form.fields[field].label if field in form.fields else ''
            for error in errors:
                messages.error(request, f'{label}: {error}')
        return redirect(back)

    data = form.cleaned_data
    mobile = data['mobile']
    needs_followup = data['needs_followup']
    # The explicit analysis controls the badge, independently of follow-up.
    # Keep older clients (without the new field) compatible.
    stage = data.get('customer_analysis') or ('potential' if needs_followup else 'lead')
    contact_type = data['call_type']
    source = data.get('source')
    due = data.get('follow_up_due')

    with transaction.atomic():
        customer = Customer.objects.select_for_update().filter(mobile=mobile).first()
        if customer is None:
            customer = Customer.objects.create(
                name=data['name'], mobile=mobile,
                source='ads' if source else 'website', ad_source=source,
                assigned_to=request.user, created_by=request.user, status='lead',
            )
        else:
            if can_edit_card(request.user, customer):
                customer.name = data['name']
            if source and can_edit_card(request.user, customer):
                customer.ad_source = source
        customer.stage = stage
        customer.needs_followup = needs_followup or customer.followups.filter(is_done=False).exists()
        customer.notes = data['notes']
        customer.save()

        call = Call.objects.create(
            customer=customer, caller_name=customer.name, call_number=mobile,
            call_date=timezone.now(),
            call_type='outgoing' if contact_type == 'followup' else 'incoming',
            contact_type=contact_type,
            purpose=data.get('purpose') or ('followup' if contact_type == 'followup' else 'sale'),
            status=data.get('call_status') or {'missed': 'missed', 'busy': 'busy'}.get(contact_type, 'answered'),
            declared_customer_status='lead' if stage == 'potential' else 'none',
            requested_condition=data.get('requested_condition') or '',
            send_address=data['send_address'], follow_up_date=due,
            follow_up_time=data.get('follow_up_time') if needs_followup else None,
            notes=data['notes'], called_by=request.user, created_by=request.user,
        )
        if needs_followup:
            FollowUp.objects.create(
                customer=customer, due_date=due, due_time=data.get('follow_up_time'),
                note=data['notes'], created_by=request.user,
            )

    messages.info(request, 'برچسب «بالقوه» ثبت شد.' if stage == 'potential' else 'مشتری با برچسب «سرنخ» ثبت شد.')
    if call.send_address:
        # Test mode only until the SMS provider is configured.
        send_address_sms(customer)
        messages.info(request, 'درخواست ارسال آدرس آزمایشی ثبت شد؛ پیامک واقعی ارسال نشده است.')
    messages.success(request, 'تماس با موفقیت ثبت شد.')

    nxt = (request.POST.get('next') or '').strip()
    prefix = reverse('customers:hub').split('/customers/')[0]
    if nxt.startswith(f'{prefix}/customers/') and '//' not in nxt:
        return redirect(nxt)
    return redirect(back)



@login_required
@require_permission('customers.view')
@require_GET
def hub_check_customer(request):
    mobile = request.GET.get('mobile', '').strip()
    if len(mobile) < 10:
        return JsonResponse({'exists': False})
    customer = Customer.objects.filter(mobile=mobile).first()
    if customer:
        return JsonResponse({
            'exists': True,
            'name': customer.name,
            'type': customer.get_customer_type_display(),
            'status': customer.get_status_display()
        })
    return JsonResponse({'exists': False})

@login_required
@require_roles(ROLE_ADMIN, ROLE_SALES_MANAGER)
@require_POST
def customer_reassign(request, pk):
    if not is_card_manager(request.user):
        raise PermissionDenied('انتقال فقط برای سرپرست و ادمین مجاز است.')
    customer = get_object_or_404(Customer, pk=pk)
    new_user_id = request.POST.get('assigned_to')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not new_user_id:
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'کارمند انتخاب نشده'}, status=400)
        return redirect('customers:detail', pk=customer.pk)

    try:
        new_user = User.objects.get(pk=new_user_id, is_active=True)
    except User.DoesNotExist:
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'کارمند یافت نشد'}, status=404)
        return redirect('customers:detail', pk=customer.pk)

    old_user = customer.assigned_to
    customer.assigned_to = new_user
    customer.save(update_fields=['assigned_to', 'updated_at'])

    old_name = old_user.get_full_name() or old_user.username if old_user else '—'
    new_name = new_user.get_full_name() or new_user.username

    if is_ajax:
        return JsonResponse({'success': True, 'message': f'مشتری از «{old_name}» به «{new_name}» ارجاع شد.'})

    messages.success(request, f'مشتری به «{new_name}» منتقل شد.')
    if request.POST.get('next') == 'hub':
        return redirect(f"{reverse('customers:hub')}?tab=info")
    return redirect('customers:detail', pk=customer.pk)

@login_required
@require_POST
@transaction.atomic
def hub_call_edit(request, pk):
    """
    ویرایش اطلاعات یک تماس گذشته از تاریخچه.
      • تماس عادی: وضعیت، هدف تماس، شرح مکالمه، تاریخ تماس
      • تماس پیگیری: تاریخ پیگیری، وضعیت پیگیری (انجام شد)، شرح مکالمه، تاریخ تماس
    """
    from calls.models import Call

    call = get_object_or_404(Call.objects.select_related('customer'), pk=pk)
    customer = call.customer
    if not can_edit_call(request.user, call):
        raise PermissionDenied('ویرایش تماس فقط برای مسئول کارت، سرپرست و ادمین مجاز است.')
    back = f"{reverse('customers:hub')}?tab=info"
    nxt = (request.POST.get('next') or '').strip()
    if nxt.startswith(reverse('customers:hub').split('/customers/')[0] + '/customers/') and '//' not in nxt:
        back = nxt

    is_followup = (call.contact_type == 'followup')

    notes = (request.POST.get('notes') or '').strip()
    if not notes:
        messages.error(request, 'شرح مکالمه اجباری است.')
        return redirect(back)

    # تاریخ تماس (شمسی → میلادی)؛ اگر خالی بود، قبلی حفظ می‌شود
    new_date = parse_jalali(request.POST.get('call_date'))
    if new_date:
        from datetime import datetime, time
        old = timezone.localtime(call.call_date) if call.call_date else timezone.localtime()
        naive = datetime.combine(new_date, old.time())
        call.call_date = timezone.make_aware(naive) if timezone.is_naive(naive) else naive

    call.notes = notes

    if is_followup:
        fu_date = parse_jalali(request.POST.get('follow_up_date'))
        fu_time = parse_followup_time(request.POST.get('follow_up_time'))
        if fu_date is None or fu_time is None:
            messages.error(request, 'تاریخ و ساعت معتبر پیگیری الزامی است.')
            return redirect(back)
        call.follow_up_date = fu_date
        call.follow_up_time = fu_time
        call.is_followed_up = bool(request.POST.get('is_followed_up'))

        # همگام‌سازی با پیگیری باز/بسته
        if call.is_followed_up:
            _close_open_followups(customer, note=notes)
        else:
            # تیک برداشته شد → پیگیری دوباره باز می‌شود
            has_open = FollowUp.objects.filter(customer=customer, is_done=False).exists()
            if not has_open:
                FollowUp.objects.create(
                    customer=customer,
                    due_date=call.follow_up_date or timezone.localdate(),
                    due_time=call.follow_up_time,
                    note=notes,
                    created_by=request.user,
                )
        _sync_needs_followup(customer)
    else:
        # تبدیل به تماس پیگیری در صورت درخواست
        if request.POST.get('needs_followup'):
            need_due = parse_jalali(request.POST.get('needs_followup_date'))
            need_time = parse_followup_time(request.POST.get('needs_followup_time'))
            if need_due is None or need_time is None:
                messages.error(request, 'برای «نیاز به پیگیری»، تاریخ پیگیری را وارد کنید.')
                return redirect(back)

            call.contact_type = 'followup'
            call.call_type = 'outgoing'
            call.purpose = 'followup'
            call.status = 'followup'
            call.follow_up_date = need_due
            call.follow_up_time = need_time
            call.is_followed_up = False
            call.save()

            FollowUp.objects.create(
                customer=customer,
                due_date=need_due,
                due_time=need_time,
                note=notes,
                created_by=request.user,
            )
            customer.needs_followup = True
            if customer.stage != 'potential':
                customer.stage = 'potential'
            customer.save(update_fields=['needs_followup', 'stage', 'notes', 'updated_at'])
            messages.success(request, 'تماس به «پیگیری» تبدیل شد و پیگیری باز ثبت شد.')
            return redirect(back)

        status = request.POST.get('status') or call.status
        if status not in ('answered', 'missed', 'busy', 'no_answer'):
            status = call.status
        call.status = status

        allowed = ['sale', 'support', 'complaint']
        if has_permission(request.user, 'customers.case'):
            allowed.append('info')
        purpose = request.POST.get('purpose') or call.purpose
        if purpose not in allowed:
            purpose = call.purpose
        call.purpose = purpose

        # شرح مشتری هم با آخرین تماس هم‌خوان بماند
        if customer.notes != notes:
            customer.notes = notes
            customer.save(update_fields=['notes', 'updated_at'])

    call.save()
    messages.success(request, 'اطلاعات تماس ویرایش شد.')
    return redirect(back)


@login_required
@require_permission('calls.edit')
@require_POST
def hub_followup_done(request, pk):
    """
    بستن یک‌کلیکی پیگیری — دکمه‌ی «انجام شد».

    ⚠️ اگر وضعیت روی «نیاز به پیگیری» (followup) بماند، Call.save()
    تیک is_followed_up را دوباره False می‌کند؛ پس وضعیت هم به
    «پاسخ داده شده» منتقل می‌شود تا رکورد واقعاً از لیست خارج شود.
    """
    call = get_object_or_404(Call.objects.select_related('customer'), pk=pk)
    if not can_edit_call(request.user, call):
        raise PermissionDenied('ویرایش پیگیری فقط برای مسئول کارت، سرپرست و ادمین مجاز است.')
    note = (request.POST.get('note') or '').strip()

    if not call.is_followed_up:
        call.is_followed_up = True
        if call.status == 'followup':
            call.status = 'answered'

        update_fields = ['is_followed_up', 'status', 'updated_at']
        if note:
            today_j = jdatetime.date.fromgregorian(date=timezone.localdate())
            line = f'نتیجه پیگیری ({today_j.strftime("%Y/%m/%d")}): {note}'
            call.notes = f'{call.notes}\n{line}'.strip() if call.notes else line
            update_fields.append('notes')

        call.save(update_fields=update_fields)
        messages.success(request, f'پیگیری «{call.caller_name}» ثبت و بسته شد.')
    else:
        messages.info(request, 'این پیگیری قبلاً بسته شده بود.')

    return redirect(f"{reverse('customers:hub')}?tab=followup")


@login_required
@require_POST
@transaction.atomic
def hub_quick_call(request, pk):
    """
    «تماس پیگیری» و «تماس جدید» از لیست مشتریان.

    kind=followup : تماس پیگیری (شرح اجباری) + منبع تماس → مشتری بالقوه می‌ماند
    kind=new      : فقط شرح مکالمه‌ی تازه؛ تاریخ تماس = همین حالا
    """
    customer = get_object_or_404(Customer.all_objects, pk=pk)
    kind = request.POST.get('kind') or 'new'
    notes = (request.POST.get('notes') or '').strip()
    back = f"{reverse('customers:hub')}?tab=info"

    needed = 'customers.followup' if kind == 'followup' else 'calls.add'
    if not has_permission(request.user, needed):
        messages.error(request, 'دسترسی لازم برای این عملیات را ندارید.')
        return redirect(back)

    if not notes:
        messages.error(request, 'شرح مکالمه اجباری است؛ ثبت انجام نشد.')
        return redirect(back)

    if kind == 'followup':
        source_id = request.POST.get('source') or ''
        if source_id.isdigit() and can_edit_card(request.user, customer):
            customer.ad_source_id = int(source_id)

        done_due = parse_jalali(request.POST.get('follow_up_date'))
        needs_next = bool(request.POST.get('needs_next'))
        next_due = parse_jalali(request.POST.get('next_follow_up_date'))

        done_time = parse_followup_time(request.POST.get('follow_up_time'))
        next_time = parse_followup_time(request.POST.get('next_follow_up_time'))
        if done_due is None or done_time is None:
            messages.error(request, 'برای تماس پیگیری، تاریخ و ساعت معتبر اجباری است.')
            return redirect(back)
        if needs_next and (next_due is None or next_time is None):
            messages.error(request, 'تاریخ و ساعت پیگیری بعدی را وارد کنید.')
            return redirect(back)

        customer.notes = notes
        customer.stage = 'potential'
        customer.save(update_fields=['notes', 'stage', 'ad_source', 'updated_at'])

        Call.objects.create(
            customer=customer,
            caller_name=customer.name,
            call_number=customer.mobile,
            call_type='outgoing',
            contact_type='followup',
            purpose='followup',
            status='followup',
            notes=notes,
            called_by=request.user,
            created_by=request.user,
            declared_customer_status='lead',
            # همین تماس نتیجه‌ی پیگیری را ثبت کرده است
            is_followed_up=True,
            follow_up_date=done_due,
            follow_up_time=done_time,
        )

        closed = _close_open_followups(customer, note=notes)

        # اگر پیگیری بازی وجود نداشت (داده‌ی قدیمی)، همین تماس را به‌عنوان
        # یک پیگیری «انجام‌شده» ثبت می‌کنیم تا وضعیت و تاریخ در لیست درست باشد
        if not closed:
            from django.utils import timezone as _tz
            FollowUp.objects.create(
                customer=customer,
                due_date=done_due,
                due_time=done_time,
                note=notes,
                is_done=True,
                done_at=_tz.now(),
                done_note=notes,
                created_by=request.user,
            )

        if needs_next:
            FollowUp.objects.create(
                customer=customer,
                due_date=next_due,
                due_time=next_time,
                note=notes,
                created_by=request.user,
            )

        _sync_needs_followup(customer)
        messages.success(request, f'پیگیری برای «{customer.name}» ثبت شد.')
        return _quick_call_redirect(request, back)

    else:
        customer.notes = notes
        customer.save(update_fields=['notes', 'updated_at'])

        # وضعیت و هدف تماس (فقط مقادیر مجاز)
        new_status = request.POST.get('status') or 'answered'
        if new_status not in ('answered', 'missed', 'busy', 'no_answer'):
            new_status = 'answered'

        allowed_purposes = ['sale', 'support', 'complaint']
        if has_permission(request.user, 'customers.case'):
            allowed_purposes.append('info')
        new_purpose = request.POST.get('purpose') or 'sale'
        if new_purpose not in allowed_purposes:
            new_purpose = 'sale'

        contact_type = request.POST.get('contact_type') or 'incoming'
        if contact_type not in dict(Call.CONTACT_TYPE_CHOICES) or contact_type == 'followup':
            contact_type = 'incoming'
        Call.objects.create(
            customer=customer,
            caller_name=customer.name,
            call_number=customer.mobile,
            call_type='incoming',
            contact_type=contact_type,
            purpose=new_purpose,
            status=new_status,
            notes=notes,
            called_by=request.user,
            created_by=request.user,
        )
        messages.success(request, f'تماس جدید برای «{customer.name}» ثبت شد.')

    return _quick_call_redirect(request, back)


from .reception_workflow import reception_action as hub_reception_action, case_save as hub_case_save
