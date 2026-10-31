from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, F, Max, Q
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.permissions import has_permission, require_permission
from .access import can_edit_card, is_card_manager
from .hiring_forms import HiringAdForm, InterviewForm, ResumeForm, role_choices, validate_national_id
from .models import (Customer, HiringAd, HiringAdSequence, HiringApplication,
                     HiringReferral, InterviewSession, Reception, RecordUpdate)


def hiring_context(request, records):
    from django import forms
    from django.core.paginator import Paginator
    from django.db.models import Exists, OuterRef, Subquery
    from django.db.models.functions import Coalesce
    from crm.numerals import digit_contains
    from .hub_views import parse_jalali
    active = InterviewSession.objects.filter(application__reception_id=OuterRef('pk'), saved_at__isnull=True)
    records = records.annotate(current_arrival=Coalesce('hiring__current_arrived_at', 'arrived_at', 'wait_started_at', 'created_at'),
                               has_active_interview=Exists(active))
    choices = records
    query = request.GET.get('workflow_q', '').strip()[:200]
    if query:
        search = digit_contains('customer__name', query) | digit_contains('customer__mobile', query)
        if has_permission(request.user, 'customers.hiring_documents'):
            search |= digit_contains('customer__national_id', query)
        records = records.filter(search)
    owner_ids = choices.values_list('customer__assigned_to_id', flat=True)
    class Filters(forms.Form):
        hiring_status = forms.ChoiceField(label='وضعیت استخدام', required=False, choices=[('', 'همه وضعیت‌ها'), ('active', 'در حال مصاحبه')] + HiringApplication.STATUSES)
        hiring_owner = forms.ModelChoiceField(label='کاربر مسئول', required=False, queryset=User.objects.filter(pk__in=owner_ids).order_by('username'))
        hiring_platform = forms.ChoiceField(label='پلتفرم آگهی', required=False, choices=[('', 'همه پلتفرم‌ها')] + HiringAd.PLATFORMS)
        hiring_ad = forms.ModelChoiceField(label='آگهی / سمت', required=False, queryset=HiringAd.objects.all())
        hiring_grade = forms.ChoiceField(label='امتیاز', required=False, choices=[('', 'همه امتیازها')] + [(x,x) for x in 'ABCDE'])
        hiring_result = forms.ChoiceField(label='نتیجه مصاحبه', required=False, choices=[('', 'همه نتایج')] + InterviewSession.RESULTS)
        hiring_date_basis = forms.ChoiceField(label='بازه تاریخ بر اساس', required=False, choices=[('arrival', 'آخرین ورود'), ('interview', 'مصاحبه ثبت‌شده'), ('next', 'مصاحبه مجدد'), ('invite', 'دعوت به همکاری')])
        hiring_from = forms.CharField(label='از تاریخ', required=False, widget=forms.TextInput(attrs={'data-jdp':'', 'autocomplete':'off'}))
        hiring_to = forms.CharField(label='تا تاریخ', required=False, widget=forms.TextInput(attrs={'data-jdp':'', 'autocomplete':'off'}))
        hiring_sort = forms.ChoiceField(label='مرتب‌سازی', required=False, choices=[('newest', 'جدیدترین ورود'), ('oldest', 'قدیمی‌ترین ورود'), ('next', 'نزدیک‌ترین مصاحبه مجدد'), ('invite', 'نزدیک‌ترین دعوت')])
    data = request.GET.copy()
    data.setdefault('hiring_date_basis', 'arrival')
    data.setdefault('hiring_sort', 'newest')
    form = Filters(data)
    for field in form.fields.values():
        field.widget.attrs['class'] = 'w-full border border-gray-200 rounded-xl px-3 py-2 text-sm'
    if form.is_valid():
        selected = form.cleaned_data
        status = selected['hiring_status']
        if status == 'active':
            records = records.filter(has_active_interview=True)
        elif status:
            condition = Q(hiring__status=status)
            if status == 'arrived':
                condition |= Q(hiring__isnull=True)
            records = records.filter(condition)
        for key, lookup in [('hiring_owner','customer__assigned_to'), ('hiring_platform','hiring__job_ad__platform'), ('hiring_ad','hiring__job_ad'), ('hiring_grade','hiring__latest_session__grade'), ('hiring_result','hiring__latest_session__result')]:
            if selected.get(key):
                records = records.filter(**{lookup:selected[key]})
        fields = {'arrival':'current_arrival', 'interview':'hiring__latest_session__started_at', 'next':'hiring__latest_session__next_interview_at', 'invite':'hiring__latest_session__invitation_at'}
        start, end = None, None
        for name, op in [('hiring_from','gte'), ('hiring_to','lte')]:
            if selected.get(name):
                date = parse_jalali(selected[name])
                if date is None:
                    form.add_error(name, 'تاریخ شمسی معتبر وارد کنید.')
                else:
                    records = records.filter(**{fields[selected['hiring_date_basis'] or 'arrival']+'__date__'+op:date})
                    if name == 'hiring_from': start = date
                    else: end = date
        if start and end and start > end:
            form.add_error('hiring_to', 'تا تاریخ نباید قبل از از تاریخ باشد.')
        sort = selected['hiring_sort']
        if sort in ('next', 'invite'):
            field = 'hiring__latest_session__next_interview_at' if sort == 'next' else 'hiring__latest_session__invitation_at'
            records = records.order_by(F(field).asc(nulls_last=True), '-pk')
        else:
            records = records.order_by('current_arrival' if sort == 'oldest' else '-current_arrival', '-pk')
    if form.errors:
        records = records.none()
    selected_pk = request.GET.get('r', '')
    selected_record = choices.filter(pk=selected_pk).first() if selected_pk.isascii() and selected_pk.isdigit() and len(selected_pk) < 16 else None
    page = Paginator(records, 30).get_page(request.GET.get('hiring_page'))
    ad_scope = Q(applications__reception__customer__is_deleted=False)
    if not is_card_manager(request.user):
        ad_scope &= Q(applications__reception__customer__assigned_to=request.user)
    ads = HiringAd.objects.select_related('created_by').annotate(applicant_count=Count('applications', filter=ad_scope, distinct=True))
    ad_query = request.GET.get('ad_q', '').strip()[:200]
    if ad_query:
        from django.db.models import CharField
        from django.db.models.functions import Cast
        ads = ads.annotate(number_text=Cast('number', CharField()))
        condition = digit_contains('role_title', ad_query) | digit_contains('email', ad_query) | digit_contains('number_text', ad_query)
        for value, title in HiringAd.PLATFORMS:
            if ad_query in title or ad_query.lower() in value.lower():
                condition |= Q(platform=value)
        ads = ads.filter(condition)
    ads_page = Paginator(ads.order_by('-created_at','-pk'), 15).get_page(request.GET.get('ad_page'))
    return {'hiring_records': page, 'hiring_choices': choices, 'hiring_selected': selected_record,
            'hiring_ads': ads_page, 'hiring_ad_query': ad_query, 'hiring_filters': form, 'hiring_filters_active': any(request.GET.get(k) for k in form.fields),
            'can_hiring_documents': has_permission(request.user, 'customers.hiring_documents')}


def destination(rec):
    return f"{reverse('customers:hub')}?tab=hiring&r={rec.pk}"


def owned_reception(request, pk, lock=False):
    records = Reception.objects.filter(person_type='interviewer', customer__is_deleted=False).select_related('customer', 'created_by', 'referred_to')
    if lock:
        records = records.select_for_update()
    if not is_card_manager(request.user):
        records = records.filter(customer__assigned_to=request.user)
    rec = get_object_or_404(records, pk=pk)
    if rec.workflow_version == 2 and not rec.referred_at:
        raise PermissionDenied('ابتدا کارجو را از پذیرش به مسئول استخدام ارجاع دهید.')
    return rec


def application_for(rec, lock=False):
    application, _ = HiringApplication.objects.get_or_create(reception=rec, defaults={'current_arrived_at': rec.arrived_at or rec.wait_started_at or rec.created_at})
    if lock:
        return HiringApplication.objects.select_for_update().get(pk=application.pk)
    return application


def save_resume(application, form, user):
    upload = form.cleaned_data.get('resume')
    if upload:
        application.resume = upload
        application.resume_name = Path(upload.name).name[:200]
        application.resume_uploaded_by = user
    if form.cleaned_data.get('job_ad'):
        application.job_ad = form.cleaned_data['job_ad']
    application.save()


def log_hiring(rec, user, label, old, new):
    RecordUpdate.objects.create(customer=rec.customer, scope='hiring', edited_by=user,
                                changes=[{'label': label, 'old': old, 'new': new}])


def session_form_response(request, rec, application, session, form=None, editing=False, status=200):
    documents = has_permission(request.user, 'customers.hiring_documents')
    if form is None:
        form = InterviewForm(instance=session, customer=rec.customer, can_documents=documents)
    return render(request, 'customers/_interview_modal.html', {
        'rec': rec, 'application': application, 'session': session, 'form': form,
        'editing_session': editing, 'can_hiring_documents': documents,
        'server_now': timezone.now().isoformat(),
    }, status=status)


@login_required
@require_permission('customers.hiring')
@require_permission('customers.hiring_interview')
@require_POST
@transaction.atomic
def interview_open(request, pk):
    rec = owned_reception(request, pk, lock=True)
    application = application_for(rec, lock=True)
    kind = request.POST.get('kind', 'first')
    if kind not in ('first', 'repeat'):
        return HttpResponse('نوع جلسه معتبر نیست.', status=400)
    session = application.sessions.filter(saved_at__isnull=True).first()
    if session:
        return session_form_response(request, rec, application, session)
    if kind == 'repeat' and application.status != 'repeat':
        return HttpResponse('مصاحبه مجدد فقط برای کارجوی دارای وضعیت مصاحبه مجدد فعال است.', status=409)
    if kind == 'first' and application.sessions.filter(saved_at__isnull=False).exists():
        return HttpResponse('جلسه اول قبلاً ثبت شده است؛ از ویرایش جلسه یا مصاحبه مجدد استفاده کنید.', status=409)
    now = timezone.now()
    arrived = application.current_arrived_at or rec.arrived_at or rec.created_at
    waiting = max(0, int((now - arrived).total_seconds())) if rec.timing_version >= 3 else (rec.wait_seconds if rec.wait_started_at and (rec.wait_ended_at or rec.workflow_version == 2 and rec.is_waiting) else rec.wait_minutes_total * 60 if rec.wait_minutes_total is not None else None)
    initial = {}
    previous = application.latest_session
    if kind == 'repeat' and previous and previous.saved_at and arrived <= previous.saved_at:
        waiting = previous.waiting_seconds
    if kind == 'repeat' and previous:
        fields = ('behavior', 'fit', 'seriousness', 'questions', 'notes', 'grade', 'result', 'rejection_reason', 'proposed_role', 'proposed_role_title', 'experience', 'next_interview_at')
        initial = {field: getattr(previous, field) for field in fields}
    number = (application.sessions.aggregate(value=Max('round_number'))['value'] or 0) + 1
    session = InterviewSession.objects.create(application=application, round_number=number, kind=kind,
        started_at=now, arrived_at=arrived, waiting_seconds=waiting,
        interviewer=request.user, job_ad=application.job_ad, **initial)
    if rec.timing_version >= 3 and rec.is_waiting:
        rec.wait_ended_at, rec.is_waiting = now, False
        rec.wait_minutes_total = waiting // 60
        rec.save(update_fields=['wait_ended_at', 'is_waiting', 'wait_minutes_total', 'updated_at'])
    log_hiring(rec, request.user, 'شروع جلسه مصاحبه', '', str(number))
    return session_form_response(request, rec, application, session)


def authorized_session(request, pk, lock=True):
    sessions = InterviewSession.objects.select_related('application__reception__customer', 'job_ad', 'interviewer')
    if lock:
        sessions = sessions.select_for_update()
    session = get_object_or_404(sessions, pk=pk)
    rec = owned_reception(request, session.application.reception_id, lock=lock)
    return rec, session.application, session


@login_required
@require_permission('customers.hiring')
@require_permission('customers.hiring_interview')
@require_POST
@transaction.atomic
def interview_end(request, pk):
    rec, application, session = authorized_session(request, pk)
    if not session.ended_at:
        session.ended_at = max(timezone.now(), session.started_at)
        session.save(update_fields=['ended_at'])
    return JsonResponse({'ended_at': session.ended_at.isoformat(), 'seconds': session.seconds,
                         'server_now': timezone.now().isoformat()})


@login_required
@require_permission('customers.hiring')
@require_GET
def interview_clock(request):
    ids = [int(value) for value in request.GET.getlist('ids')[:100] if value.isascii() and value.isdigit() and len(value) < 16]
    sessions = InterviewSession.objects.filter(pk__in=ids, application__reception__customer__is_deleted=False)
    if not is_card_manager(request.user):
        sessions = sessions.filter(application__reception__customer__assigned_to=request.user)
    return JsonResponse({'server_now':timezone.now().isoformat(), 'sessions':list(sessions.values('pk','started_at','ended_at'))}, headers={'Cache-Control':'no-store'})


def persist_session(request, rec, application, session, editing=False):
    if session.saved_at and not editing:
        return redirect(destination(rec))
    if editing and application.latest_session_id != session.pk:
        return HttpResponse('جلسات قبلی فقط در تاریخچه قابل مشاهده‌اند.', status=409)
    form = InterviewForm(request.POST, instance=session, customer=rec.customer,
                         can_documents=has_permission(request.user, 'customers.hiring_documents'))
    valid = form.is_valid()
    resume_form = None
    if has_permission(request.user, 'customers.hiring_documents') and request.FILES.get('resume'):
        resume_form = ResumeForm({}, request.FILES)
        if not resume_form.is_valid():
            form.add_error(None, resume_form.errors.as_text())
            valid = False
    if not valid:
        return session_form_response(request, rec, application, session, form=form, editing=editing, status=400)
    session = form.save(commit=False)
    session.next_interview_at = form.cleaned_data['next_interview_at']
    session.invitation_at = form.cleaned_data['invitation_at']
    session.proposed_role_title = dict(form.fields['proposed_role'].choices).get(session.proposed_role, '') if session.proposed_role else ''
    session.invited_by = rec.customer.assigned_to if session.invite else None
    now = timezone.now()
    if not session.ended_at:
        session.ended_at = max(now, session.started_at)
    if not session.saved_at:
        session.saved_at = max(now, session.ended_at)
    session.saved_by = request.user
    session.save()
    if 'national_id' in form.cleaned_data:
        customer = Customer.all_objects.select_for_update().get(pk=rec.customer_id)
        customer.national_id = form.cleaned_data['national_id']
        customer.save(update_fields=['national_id', 'updated_at'])
    before = application.get_status_display()
    application.job_ad = session.job_ad
    application.latest_session = session
    application.status = 'invited' if session.invite else {'accepted': 'interviewed', 'repeat': 'repeat', 'rejected': 'rejected'}[session.result]
    application.save()
    if resume_form:
        save_resume(application, resume_form, request.user)
    log_hiring(rec, request.user, f'نتیجه جلسه {session.round_number}', before, application.get_status_display())
    messages.success(request, 'اطلاعات جلسه ذخیره شد؛ زمان مصاحبه ثبت و تایمر متوقف شد.')
    return redirect(destination(rec))


@login_required
@require_permission('customers.hiring')
@require_permission('customers.hiring_interview')
@require_POST
@transaction.atomic
def interview_save(request, pk):
    return persist_session(request, *authorized_session(request, pk))


@login_required
@require_permission('customers.hiring')
@require_permission('customers.hiring_interview')
@transaction.atomic
def interview_edit(request, pk):
    if request.method not in ('GET', 'POST'):
        return HttpResponse(status=405)
    rec, application, session = authorized_session(request, pk)
    if not session.saved_at or application.latest_session_id != session.pk:
        return HttpResponse('این جلسه برای ویرایش نهایی آماده نیست.', status=409)
    if request.method == 'POST':
        return persist_session(request, rec, application, session, editing=True)
    return session_form_response(request, rec, application, session, editing=True)


@login_required
@require_permission('customers.hiring')
@require_permission('customers.hiring_interview')
@require_permission('customers.hiring_documents')
@require_POST
@transaction.atomic
def hiring_identity(request, pk):
    rec = owned_reception(request, pk, lock=True)
    from django.core.exceptions import ValidationError
    try:
        national_id = validate_national_id(request.POST.get('national_id', ''), rec.customer)
    except ValidationError as error:
        return JsonResponse({'error': ' '.join(error.messages)}, status=400)
    rec.customer.national_id = national_id
    rec.customer.save(update_fields=['national_id', 'updated_at'])
    return JsonResponse({'success': True, 'message': 'کد ملی ثبت شد.'})


@login_required
@require_permission('customers.hiring')
@require_permission('customers.hiring_documents')
@require_GET
def hiring_resume(request, pk):
    rec = owned_reception(request, pk)
    application = get_object_or_404(HiringApplication, reception=rec)
    if not application.resume:
        return HttpResponse('رزومه‌ای ثبت نشده است.', status=404)
    response = FileResponse(application.resume.open('rb'), as_attachment=True, filename=application.resume_name or 'resume')
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
@require_permission('customers.hiring')
@require_permission('customers.hiring_interview')
@require_permission('customers.hiring_documents')
@require_POST
@transaction.atomic
def hiring_resume_upload(request, pk):
    rec = owned_reception(request, pk, lock=True)
    form = ResumeForm(request.POST, request.FILES)
    if not form.is_valid() or not form.cleaned_data.get('resume'):
        return JsonResponse({'error': str(form.errors.as_text()) or 'فایل رزومه را انتخاب کنید.'}, status=400)
    save_resume(application_for(rec, lock=True), form, request.user)
    return JsonResponse({'success': True, 'message': 'رزومه ثبت شد.'})


@login_required
@require_permission('customers.hiring')
@require_permission('customers.hiring_refer')
@transaction.atomic
def hiring_refer(request, pk):
    from .reception_workflow import referral_users
    if request.method not in ('GET', 'POST'):
        return HttpResponse(status=405)
    rec = owned_reception(request, pk, lock=True)
    choices = referral_users('interviewer')
    error = ''
    if request.method == 'POST':
        target = next((user for user in choices if str(user.pk) == request.POST.get('user')), None)
        if target is None:
            error = 'مسئول فعال و دارای مجوز مصاحبه را انتخاب کنید.'
        else:
            application = application_for(rec, lock=True)
            old_user = rec.customer.assigned_to
            if not old_user or old_user.pk != target.pk:
                HiringReferral.objects.create(application=application, from_user=old_user, to_user=target, actor=request.user, note=request.POST.get('note', '').strip())
                rec.customer.assigned_to = target
                rec.customer.save(update_fields=['assigned_to', 'updated_at'])
                log_hiring(rec, request.user, 'ارجاع استخدام', str(old_user or ''), str(target))
            messages.success(request, 'کارجو ارجاع شد؛ این عملیات تایمری شروع نمی‌کند.')
            return redirect(destination(rec))
    return render(request, 'customers/_hiring_referral_modal.html', {'rec': rec, 'users': choices, 'error': error}, status=400 if error else 200)


@login_required
@require_permission('customers.hiring')
@require_permission('customers.hiring_ads')
@transaction.atomic
def hiring_ad_create(request):
    if request.method not in ('GET', 'POST'):
        return HttpResponse(status=405)
    form = HiringAdForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        ad = form.save(commit=False)
        start = HiringAd.STARTS[ad.platform]
        maximum = HiringAd.objects.filter(platform=ad.platform).aggregate(value=Max('number'))['value']
        sequence, _ = HiringAdSequence.objects.select_for_update().get_or_create(platform=ad.platform, defaults={'next_number': max(start, (maximum or start - 1) + 1)})
        HiringAdSequence.objects.filter(pk=sequence.pk).update(next_number=F('next_number') + 1)
        sequence.refresh_from_db()
        ad.number = sequence.next_number - 1
        ad.role_title = dict(form.fields['role_key'].choices)[ad.role_key]
        ad.created_by = request.user
        ad.save()
        messages.success(request, f'آگهی استخدام {ad.get_platform_display()} با شناسه {ad.number} ثبت شد.')
        return redirect(f"{reverse('customers:hub')}?tab=hiring")
    return render(request, 'customers/_hiring_ad_modal.html', {'form': form, 'ads': HiringAd.objects.select_related('created_by').order_by('-created_at')[:30]}, status=400 if form.errors else 200)
