from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q, OuterRef, Subquery, Count
from django.db.models.functions import Coalesce
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from accounts.permissions import has_permission, require_permission
from crm.pagination import paginate
from crm.numerals import digit_contains
from .access import is_card_manager, can_edit_card
from .models import Customer, Reception, InterviewSession, RecordUpdate, HiringReferral
from .forms import HubCallForm


@login_required
@require_permission('customers.candidate_view')
def candidate_list(request):
    if has_permission(request.user,'customers.info'):
        from .hub_views import customer_hub
        request.GET=request.GET.copy();request.GET['tab']='info';request.GET['people']='candidates'
        return customer_hub(request)
    context=candidate_list_context(request)
    context['call_form']=HubCallForm(user=request.user)
    return render(request,'customers/candidate_list.html',context)


def candidate_queryset(user):
    people = Customer.objects.filter(is_interviewer=True).select_related('assigned_to')
    if not is_card_manager(user):
        people = people.filter(Q(assigned_to=user)|Q(created_by=user))
    latest=Reception.objects.filter(customer_id=OuterRef('pk'),person_type='interviewer').annotate(
        list_arrival=Coalesce('hiring__current_arrived_at','arrived_at','created_at')).order_by('-created_at','-pk')
    people=people.annotate(candidate_reception_id=Subquery(latest.values('pk')[:1]),
                          candidate_arrival=Subquery(latest.values('list_arrival')[:1]),
                          candidate_referred_at=Subquery(latest.values('referred_at')[:1]))
    return people


def prepare_candidate_actions(user, page):
    from django.urls import reverse
    can_admit=has_permission(user,'customers.reception') and has_permission(user,'customers.reception_add')
    manager=is_card_manager(user)
    can_hiring=has_permission(user,'customers.hiring')
    for person in page:
        person.candidate_reception_url=(reverse('customers:hub')+f'?tab=reception&c={person.pk}') if can_admit else ''
        person.candidate_hiring_url=(reverse('customers:hub')+f'?tab=hiring&r={person.candidate_reception_id}') if person.candidate_referred_at and can_hiring and (manager or person.assigned_to_id==user.pk) else ''


def candidate_list_context(request):
    if not has_permission(request.user,'customers.candidate_view'):
        raise PermissionDenied
    people = candidate_queryset(request.user)
    stats=people.aggregate(total=Count('pk'),registered=Count('pk',filter=Q(candidate_reception_id__isnull=True)),
        admitted=Count('pk',filter=Q(candidate_reception_id__isnull=False)),referred=Count('pk',filter=Q(candidate_referred_at__isnull=False)))
    owner_ids=people.values('assigned_to_id')
    from django.contrib.auth.models import User
    owners=User.objects.filter(pk__in=owner_ids).order_by('first_name','username')
    query = request.GET.get('q','').strip()[:200]
    if query:
        people = people.filter(digit_contains('name',query)|digit_contains('mobile',query))
    visit=request.GET.get('visit','')
    if visit=='registered':people=people.filter(candidate_reception_id__isnull=True)
    elif visit=='admitted':people=people.filter(candidate_reception_id__isnull=False,candidate_referred_at__isnull=True)
    elif visit=='referred':people=people.filter(candidate_referred_at__isnull=False)
    owner=request.GET.get('contact_expert','')
    if owner=='unassigned':people=people.filter(assigned_to__isnull=True)
    elif owner:people=people.filter(assigned_to_id=owner) if owner.isascii() and owner.isdigit() and len(owner)<16 else people.none()
    from audit.views import _parse_jalali_date
    start_raw,end_raw=request.GET.get('date_from',''),request.GET.get('date_to','')
    start,end=_parse_jalali_date(start_raw),_parse_jalali_date(end_raw)
    if (start_raw and not start) or (end_raw and not end) or (start and end and start>end):
        people=people.none()
        messages.error(request,'بازه تاریخ معتبر نیست؛ تاریخ شمسی شروع و پایان را بررسی کنید.')
    else:
        if start:people=people.filter(created_at__date__gte=start)
        if end:people=people.filter(created_at__date__lte=end)
    mode='oldest' if request.GET.get('display_mode')=='oldest' else 'recent'
    page=paginate(request,people.order_by('created_at' if mode=='oldest' else '-created_at','pk' if mode=='oldest' else '-pk'))
    prepare_candidate_actions(request.user, page)
    return {'people':page,'customers':page,'candidate_mode':True,'search':query,'candidate_stats':stats,'contact_experts':owners,
        'table_filters':{'display_mode':mode,'date_from':start_raw,'date_to':end_raw,'contact_expert':owner,'visit':visit},'show_new':False}


def profile(request, person):
    if not has_permission(request.user,'customers.candidate_view') or not (
        can_edit_card(request.user,person) or person.created_by_id == request.user.pk
    ):
        raise PermissionDenied
    can_hiring = has_permission(request.user,'customers.hiring') and can_edit_card(request.user,person)
    records = Reception.objects.filter(customer=person,person_type='interviewer').select_related('created_by','referred_by','referred_to','hiring','hiring__job_ad','hiring__latest_session').order_by('-created_at','-pk')
    latest = records.first()
    sessions = InterviewSession.objects.filter(application__reception__customer=person).select_related('interviewer','job_ad').order_by('-started_at','-pk') if can_hiring else InterviewSession.objects.none()
    referrals = HiringReferral.objects.filter(application__reception__customer=person).select_related('from_user','to_user','actor').order_by('-created_at','-pk') if can_hiring else HiringReferral.objects.none()
    can_edit = has_permission(request.user,'customers.candidate_edit') and can_edit_card(request.user,person)
    form = None
    if request.method == 'POST':
        if not can_edit:
            raise PermissionDenied
        data=request.POST.copy();data['is_interviewer']='on'
        form=HubCallForm(data,user=request.user)
        if form.is_valid():
            if Customer.all_objects.filter(mobile=form.cleaned_data['mobile']).exclude(pk=person.pk).exists():
                form.add_error('mobile','این شماره برای فرد دیگری ثبت شده است.')
            else:
                before=f'{person.name} — {person.mobile}'
                person.name,person.mobile=form.cleaned_data['name'],form.cleaned_data['mobile']
                person.save(update_fields=['name','mobile','updated_at'])
                RecordUpdate.objects.create(customer=person,scope='hiring',edited_by=request.user,
                    changes=[{'label':'هویت مصاحبه‌کننده','old':before,'new':f'{person.name} — {person.mobile}'}])
                request.feedback_context={'form':'#candidate-identity-form'}
                messages.success(request,'نام و شماره مصاحبه‌کننده ذخیره شد.')
                return redirect('customers:detail',pk=person.pk)
    elif can_edit:
        form=HubCallForm(initial={'name':person.name,'mobile':person.mobile})
    if form:
        for name in ('name','mobile'):
            for attr in list(form.fields[name].widget.attrs):
                if attr.startswith(('@',':','x-')):
                    form.fields[name].widget.attrs.pop(attr)
    return render(request,'customers/candidate_detail.html',{'person':person,'latest':latest,'records':paginate(request,records,'visits_page'),
        'sessions':paginate(request,sessions,'sessions_page'),'referrals':paginate(request,referrals,'referrals_page'),'can_hiring':can_hiring,'can_edit_candidate':can_edit,'identity_form':form,
        'can_documents':can_hiring and has_permission(request.user,'customers.hiring_documents') and latest and (latest.referred_at or latest.workflow_version == 1)})
