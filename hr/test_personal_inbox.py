from datetime import timedelta
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import UserPermissionOverride
from accounts.permissions import ROLE_TO_GROUP
from .models import Employee, Task, TaskEvent, TaskNotice, TaskReport


class PersonalInboxTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('personal_manager')
        self.other = User.objects.create_user('personal_other')
        self.other.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['support'])[0])
        self.client.force_login(self.user)
        self.url = reverse('hr:task_inbox')

    def get(self, **params):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code,200)
        return response.json()

    def report_request(self, task):
        return TaskEvent.objects.create(task=task,to_status='follow_up',report_user=self.user,report_required=True,snapshot={'title':task.title,'description':'شرح هنگام انجام کار'})

    def test_badge_counts_unique_actionable_tasks_instead_of_notices_or_events(self):
        task=Task.objects.create(title='یک کار',assigned_user=self.user)
        TaskNotice.objects.create(task=task,user=self.user,text='تغییر دوم')
        self.report_request(task);self.report_request(task)
        data=self.get()
        self.assertEqual(data['attention_count'],1)
        self.assertEqual(data['counts']['work'],1)
        self.assertEqual(data['counts']['reports'],1)
        self.assertEqual(data['pending_reports'],2)
        self.assertEqual(data['items'][0]['report_count'],2)
        self.assertEqual(len(self.get(view='reports')['items']),1)

    def test_personal_queue_excludes_other_members_even_for_manager(self):
        own=Task.objects.create(title='کار مدیر',assigned_user=self.user)
        Task.objects.create(title='کار دیگری',assigned_user=self.other)
        self.assertEqual([row['task'] for row in self.get()['items']],[own.pk])
        response=self.client.get(reverse('hr:task_list'),{'scope':'mine'})
        self.assertEqual(list(response.context['page_obj']),[own])
        self.assertContains(response,'name="scope" value="mine"')
        self.assertEqual(self.get()['attention_count'],1)

    def test_pending_reports_for_work_performed_on_behalf_of_another_are_included(self):
        task=Task.objects.create(title='کار انجام‌شده برای دیگری',assigned_user=self.other,status='done')
        event=self.report_request(task)
        data=self.get(view='reports')
        self.assertEqual(data['counts']['work'],0)
        self.assertEqual(data['attention_count'],1)
        self.assertEqual(data['items'][0]['report']['event'],event.pk)
        self.assertEqual(data['items'][0]['report']['description'],'شرح هنگام انجام کار')

    def test_reading_updates_does_not_finish_work_or_remove_report_requests(self):
        task=Task.objects.create(title='کار باز',assigned_user=self.user)
        self.report_request(task)
        TaskNotice.objects.create(task=task,user=self.other,text='اعلان شخص دیگر')
        response=self.client.post(reverse('hr:task_notice_read'),{'scope':'all'})
        self.assertEqual(response.status_code,200)
        task.refresh_from_db();self.assertEqual(task.status,'pending')
        data=self.get()
        self.assertEqual(data['attention_count'],1)
        self.assertEqual(data['counts']['updates_unread'],0)
        self.assertEqual(data['pending_reports'],1)
        self.assertTrue(TaskNotice.objects.filter(user=self.other,read_at__isnull=True).exists())

    def test_updates_are_grouped_per_task_and_read_button_reads_only_that_task(self):
        first=Task.objects.create(title='اول',assigned_user=self.user)
        second=Task.objects.create(title='دوم',assigned_user=self.user)
        latest=TaskNotice.objects.create(task=first,user=self.user,text='آخرین تغییر اول')
        data=self.get(view='updates')
        self.assertEqual(len(data['items']),2)
        self.assertEqual(data['items'][0]['summary'],'آخرین تغییر اول')
        self.assertEqual(self.client.post(reverse('hr:task_notice_read'),{'notice':latest.pk}).status_code,200)
        self.assertFalse(TaskNotice.objects.filter(task=first,user=self.user,read_at__isnull=True).exists())
        self.assertTrue(TaskNotice.objects.filter(task=second,user=self.user,read_at__isnull=True).exists())
        self.assertEqual(self.get()['attention_count'],2)

    def test_work_does_not_disappear_when_no_unread_notice_exists(self):
        task=Task.objects.create(title='کاری که اعلانش خوانده شده',assigned_user=self.user)
        task.notices.update(read_at=timezone.now())
        data=self.get()
        self.assertEqual(data['unread'],0)
        self.assertEqual(data['attention_count'],1)
        self.assertEqual(data['items'][0]['task'],task.pk)

    def test_due_filters_priority_and_pagination(self):
        today=timezone.localdate()
        late=Task.objects.create(title='عقب‌افتاده',assigned_user=self.user,due_date=today-timedelta(days=1))
        now=Task.objects.create(title='امروز',assigned_user=self.user,due_date=today)
        future=Task.objects.create(title='آینده',assigned_user=self.user,due_date=today+timedelta(days=1))
        for i in range(12):Task.objects.create(title='کار بدون موعد '+str(i),assigned_user=self.user)
        data=self.get(sort='overdue');self.assertEqual(data['items'][0]['task'],late.pk)
        self.assertEqual(data['pagination']['total'],15);self.assertEqual(len(data['items']),10)
        self.assertEqual(len(self.get(page=2)['items']),5)
        self.assertEqual([row['task'] for row in self.get(due='overdue')['items']],[late.pk])
        self.assertEqual([row['task'] for row in self.get(due='today')['items']],[now.pk])
        self.assertEqual([row['task'] for row in self.get(due='upcoming')['items']],[future.pk])
        self.assertEqual(self.get(due='undated')['pagination']['total'],12)

    def test_new_tasks_first_and_same_sort_on_full_page(self):
        old=Task.objects.create(title='قدیمی', assigned_user=self.user, priority='urgent')
        new=Task.objects.create(title='جدید', assigned_user=self.user, priority='low')
        self.assertEqual([row['task'] for row in self.get()['items']], [new.pk, old.pk])
        self.assertEqual(self.get(sort='priority')['items'][0]['task'], old.pk)
        response=self.client.get(reverse('hr:task_list'), {'scope':'mine'})
        self.assertEqual([task.pk for task in response.context['page_obj']], [new.pk, old.pk])

    def test_date_ranges_creation_and_due_are_distinct_and_invalid_dates_visible(self):
        from dashboard.templatetags.fa_numbers import jdate
        today=timezone.localdate()
        date=jdate(today,'Y/m/d')
        task=Task.objects.create(title='موعد فردا',assigned_user=self.user,due_date=today+timedelta(days=1))
        self.assertEqual(self.get(date_from=date,date_to=date)['items'][0]['task'],task.pk)
        self.assertEqual(self.get(date_basis='due',date_from=date,date_to=date)['items'],[])
        invalid=self.get(date_from='invalid')
        self.assertEqual(invalid['items'],[])
        self.assertIn('date_from',invalid['filter_errors'])
        response=self.client.get(reverse('hr:task_list'), {'scope':'mine','date_basis':'due','date_to':date})
        self.assertEqual(len(response.context['page_obj']),0)

    def test_closed_work_is_not_actionable_but_history_remains(self):
        task=Task.objects.create(title='تمام شده',assigned_user=self.user,status='done')
        TaskNotice.objects.create(task=task,user=self.user,text='اتمام کار')
        data=self.get()
        self.assertEqual(data['attention_count'],0);self.assertEqual(data['items'],[])
        self.assertEqual(len(self.get(view='updates')['items']),1)

    def test_search_supports_persian_digits_and_never_returns_other_members_tasks(self):
        own=Task.objects.create(title='پرونده 123',assigned_user=self.user)
        Task.objects.create(title='پرونده 123 دیگر',assigned_user=self.other)
        data=self.get(q='۱۲۳')
        self.assertEqual([row['task'] for row in data['items']],[own.pk])
        self.assertEqual(self.get(q='بدون نتیجه')['items'],[])
        self.assertEqual(data['counts']['work'],1)

    def test_report_permission_denial_hides_pending_report_items(self):
        task=Task.objects.create(title='گزارش خصوصی',assigned_user=self.other,status='done')
        event=TaskEvent.objects.create(task=task,to_status='done',report_user=self.other,report_required=True)
        UserPermissionOverride.objects.create(user=self.other,permission_key='hr.report_tasks',granted=False)
        self.client.force_login(self.other)
        data=self.get(view='reports')
        self.assertEqual(data['reports'],[]);self.assertEqual(data['items'],[])
        self.assertEqual(data['counts']['reports'],0)

    def test_ordinary_member_counts_use_their_distinct_permission_scope(self):
        task=Task.objects.create(title='وظیفه کارشناس',assigned_user=self.other)
        TaskEvent.objects.create(task=task,to_status='follow_up',report_user=self.other,report_required=True)
        self.client.force_login(self.other)
        data=self.get()
        self.assertEqual(data['attention_count'],1)
        self.assertEqual(data['counts']['work'],1)
        self.assertEqual(data['counts']['reports'],1)
        self.assertEqual(data['counts']['updates_unread'],1)
