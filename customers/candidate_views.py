from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
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
    people = Customer.objects.filter(is_interviewer=True).select_related('assigned_to')
    if not is_card_manager(request.user):
        people = people.filter(Q(assigned_to=request.user)|Q(created_by=request.user))
    query = request.GET.get('q','').strip()[:200]
    if query:
        people = people.filter(digit_contains('name',query)|digit_contains('mobile',query))
    return render(request,'customers/candidate_list.html',{'people':paginate(request,people.order_by('-created_at','-pk')),'search':query})


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
