from django import forms
from django.db.models import Case, IntegerField, Value, When, F
from audit.views import _parse_jalali_date
from .task_access import overdue_condition


class TaskQueueFilters(forms.Form):
    sort = forms.ChoiceField(label='ترتیب نمایش', required=False, initial='newest', choices=[
        ('newest', 'جدیدترین تسک'), ('oldest', 'قدیمی‌ترین تسک'), ('due', 'نزدیک‌ترین موعد'),
        ('overdue', 'عقب‌افتاده و امروز'), ('priority', 'بالاترین اولویت'), ('workflow','ترتیب مراحل کاری')])
    source=forms.ChoiceField(label='بخش / مرحله',required=False,choices=[])
    status=forms.ChoiceField(label='وضعیت',required=False,choices=[])
    priority=forms.ChoiceField(label='اولویت',required=False,choices=[])

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        from .models import Task
        self.fields['source'].choices=[('','همه بخش‌ها')]+TASK_SOURCES
        self.fields['status'].choices=[('','همه وضعیت‌ها')]+Task.STATUS_CHOICES
        self.fields['priority'].choices=[('','همه اولویت‌ها')]+Task.PRIORITY_CHOICES

    date_basis = forms.ChoiceField(label='تاریخ براساس', required=False, initial='created',
                                  choices=[('created', 'تاریخ ایجاد وظیفه'), ('due', 'موعد انجام وظیفه')])
    date_from = forms.CharField(label='از تاریخ', required=False, widget=forms.TextInput(attrs={'data-jdp': '', 'placeholder': 'انتخاب تاریخ…'}))
    date_to = forms.CharField(label='تا تاریخ', required=False, widget=forms.TextInput(attrs={'data-jdp': '', 'placeholder': 'انتخاب تاریخ…'}))

    def clean(self):
        data = super().clean()
        for key in ('date_from', 'date_to'):
            raw = data.get(key)
            data[key] = _parse_jalali_date(raw) if raw else None
            if raw and not data[key]:
                self.add_error(key, 'تاریخ شمسی معتبر وارد کنید.')
        if data.get('date_from') and data.get('date_to') and data['date_from'] > data['date_to']:
            self.add_error('date_to', 'پایان بازه نباید قبل از شروع باشد.')
        return data


def filter_task_dates(items, data, prefix=''):
    field = prefix + ('due_date' if data.get('date_basis') == 'due' else 'created_at__date')
    for key, lookup in [('date_from', 'gte'), ('date_to', 'lte')]:
        if data.get(key):
            items = items.filter(**{field + '__' + lookup: data[key]})
    return items


def order_tasks(items, sort, prefix=''):
    from django.utils import timezone
    def key(name): return prefix + name
    from django.db.models import Q
    now=timezone.localtime()
    late=(Q(**{key('due_date__lt'):now.date()}) | Q(**{key('due_date'):now.date(),key('due_time__lt'):now.time().replace(tzinfo=None)})) & ~Q(**{key('status__in'):['done','cancelled']})
    items = items.annotate(
        _queue_priority=Case(When(**{key('priority'):'urgent'}, then=Value(0)), When(**{key('priority'):'high'}, then=Value(1)),
                             When(**{key('priority'):'medium'}, then=Value(2)), default=Value(3), output_field=IntegerField()),
        _queue_due=Case(When(late, then=Value(0)), When(**{key('due_date'):timezone.localdate()}, then=Value(1)),
                        When(**{key('due_date__isnull'):True}, then=Value(3)), default=Value(2), output_field=IntegerField()),
    )
    items=items.annotate(_queue_stage=Case(*[When(**{key('source_type'):kind},then=Value(i)) for i,kind in enumerate(['admission','reception','registration','case','interview','invitation'])],default=Value(99),output_field=IntegerField()))
    orders = {
        'newest': ['-'+key('created_at'), '-'+key('pk')], 'oldest': [key('created_at'), key('pk')],
        'due': [F(key('due_date')).asc(nulls_last=True), F(key('due_time')).asc(nulls_last=True), '-pk'],
        'overdue': ['_queue_due', key('due_date'), key('due_time'), '-'+key('pk')],
        'workflow': ['_queue_stage','_queue_priority','-'+key('created_at'),'-'+key('pk')],
        'priority': ['_queue_priority', F(key('due_date')).asc(nulls_last=True), '-pk'],
    }
    return items.order_by(*orders.get(sort, orders['newest']))


TASK_SOURCES=[('manual','وظیفه دستی'),('admission','ثبت ورود در پذیرش'),('reception','ارجاع پذیرش'),
              ('registration','ثبت اطلاعات'),('case','تکمیل پرونده'),('followup','پیگیری مشتری'),
              ('interview','مصاحبه اول'),('repeat','مصاحبه مجدد'),('invitation','دعوت به همکاری'),
              ('call','تماس'),('invoice','فاکتور'),('leave','مرخصی'),('structure','فرآیند سفارشی')]


def filter_task_source(items,source,prefix=''):
    from django.db.models import Q
    key=lambda name:prefix+name
    if source=='manual':return items.filter(**{key('source_type'):'',key('hiring_session__isnull'):True})
    if source=='repeat':return items.filter(**{key('hiring_session__isnull'):False})
    if source=='followup':return items.filter(**{key('source_type__in'):['followup','customer_followup']})
    if source=='interview':return items.filter(**{key('source_type'):'interview',key('hiring_session__isnull'):True})
    if source in dict(TASK_SOURCES):return items.filter(**{key('source_type'):source})
    return items


def available_sources(records):
    kinds=set(records.values_list('source_type',flat=True))
    available=kinds|({'manual'} if '' in kinds else set())|({'followup'} if 'customer_followup' in kinds else set())
    if records.filter(hiring_session__isnull=False).exists():available.add('repeat')
    return [(key,label) for key,label in TASK_SOURCES if key in available]


def filter_task_properties(items,data,prefix=''):
    items=filter_task_source(items,data.get('source'),prefix)
    for name in ('status','priority'):
        if data.get(name):items=items.filter(**{prefix+name:data[name]})
    return items
