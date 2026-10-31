from django import forms
from django.contrib.auth.models import User
from django.db.models import Exists, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce

from .models import CaseWorkSession


def filter_workflow_records(request, records, stage):
    from .hub_views import parse_jalali
    owners = records.values_list('customer__assigned_to_id', flat=True)
    status_choices = {
        'reception': [('pending','در انتظار ارجاع'), ('referred','ارجاع شده')],
        'case': [('pending','تکمیل نشده'), ('active','تایمر در حال اجرا'), ('done','پرونده ثبت شده')],
        'registration': [('pending','ثبت نشده'), ('done','اطلاعات ثبت شده')],
    }
    class Filters(forms.Form):
        workflow_owner = forms.ModelChoiceField(label='کاربر مسئول', required=False, queryset=User.objects.filter(pk__in=owners).order_by('username'))
        workflow_person = forms.ChoiceField(label='نوع مراجعه‌کننده', required=False, choices=[('', 'همه افراد'), ('customer','مشتری'), ('interviewer','مصاحبه‌کننده')])
        workflow_status = forms.ChoiceField(label='وضعیت مرحله', required=False, choices=[('', 'همه وضعیت‌ها')] + status_choices[stage])
        workflow_date_basis = forms.ChoiceField(label='تاریخ بر اساس', required=False, choices=[('arrival','ورود'), ('referral','ارجاع'), ('case','ثبت پرونده'), ('registration','ثبت اطلاعات'), ('work','شروع تکمیل پرونده')])
        workflow_from = forms.CharField(label='از تاریخ', required=False, widget=forms.TextInput(attrs={'data-jdp':'', 'autocomplete':'off'}))
        workflow_to = forms.CharField(label='تا تاریخ', required=False, widget=forms.TextInput(attrs={'data-jdp':'', 'autocomplete':'off'}))
    data = request.GET.copy()
    data.setdefault('workflow_date_basis', 'arrival')
    form = Filters(data)
    if stage != 'reception':
        form.fields.pop('workflow_person')
    for field in form.fields.values():
        field.widget.attrs['class'] = 'w-full border border-gray-200 rounded-xl px-3 py-2 text-sm'
    active_work = CaseWorkSession.objects.filter(reception=OuterRef('pk'), ended_at__isnull=True)
    records = records.annotate(workflow_arrival=Coalesce('hiring__current_arrived_at', 'arrived_at', 'wait_started_at', 'created_at'),
                               workflow_work=Subquery(CaseWorkSession.objects.filter(reception=OuterRef('pk')).order_by('-started_at','-pk').values('started_at')[:1]),
                               workflow_work_active=Exists(active_work))
    if form.is_valid():
        values = form.cleaned_data
        if values.get('workflow_owner'):
            records = records.filter(customer__assigned_to=values['workflow_owner'])
        if values.get('workflow_person'):
            records = records.filter(person_type=values['workflow_person'])
        status = values['workflow_status']
        if status and stage == 'reception':
            records = records.filter(referred_at__isnull=status=='pending')
        elif status and stage == 'case':
            records = records.filter(workflow_work_active=True) if status == 'active' else records.filter(case_completed_at__isnull=status=='pending')
        elif status and stage == 'registration':
            records = records.filter(registration_completed_at__isnull=status=='pending')
        basis = {'arrival':'workflow_arrival', 'referral':'referred_at', 'case':'case_completed_at', 'registration':'registration_completed_at', 'work':'workflow_work'}[values['workflow_date_basis'] or 'arrival']
        start, end = None, None
        for name, operation in [('workflow_from','gte'), ('workflow_to','lte')]:
            if values.get(name):
                date = parse_jalali(values[name])
                if date is None:
                    form.add_error(name, 'تاریخ شمسی معتبر وارد کنید.')
                else:
                    records = records.filter(**{basis+'__date__'+operation:date})
                    if name == 'workflow_from': start = date
                    else: end = date
        if start and end and start > end:
            form.add_error('workflow_to', 'تا تاریخ نباید قبل از از تاریخ باشد.')
    if form.errors:
        records = records.none()
    return records, form
