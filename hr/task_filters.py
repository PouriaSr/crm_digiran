from django import forms
from django.db.models import Case, IntegerField, Value, When, F
from audit.views import _parse_jalali_date
from .task_access import overdue_condition


class TaskQueueFilters(forms.Form):
    sort = forms.ChoiceField(label='ترتیب نمایش', required=False, initial='newest', choices=[
        ('newest', 'جدیدترین تسک'), ('oldest', 'قدیمی‌ترین تسک'), ('due', 'نزدیک‌ترین موعد'),
        ('overdue', 'عقب‌افتاده و امروز'), ('priority', 'بالاترین اولویت')])
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


def order_tasks(items, sort):
    from django.utils import timezone
    items = items.annotate(
        _queue_priority=Case(When(priority='urgent', then=Value(0)), When(priority='high', then=Value(1)),
                             When(priority='medium', then=Value(2)), default=Value(3), output_field=IntegerField()),
        _queue_due=Case(When(overdue_condition(), then=Value(0)), When(due_date=timezone.localdate(), then=Value(1)),
                        When(due_date__isnull=True, then=Value(3)), default=Value(2), output_field=IntegerField()),
    )
    orders = {
        'newest': ['-created_at', '-pk'], 'oldest': ['created_at', 'pk'],
        'due': [F('due_date').asc(nulls_last=True), F('due_time').asc(nulls_last=True), '-pk'],
        'overdue': ['_queue_due', 'due_date', 'due_time', '-pk'],
        'priority': ['_queue_priority', F('due_date').asc(nulls_last=True), '-pk'],
    }
    return items.order_by(*orders.get(sort, orders['newest']))
