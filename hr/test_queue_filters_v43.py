from datetime import timedelta
import jdatetime
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from hr.models import Task, TaskEvent


class TaskQueueConsistencyTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_superuser('queue_consistent_admin')
        self.client.force_login(self.user)
        self.old=Task.objects.create(title='قدیمی با اولویت بالا',assigned_user=self.user,priority='urgent',due_date=timezone.localdate())
        self.new=Task.objects.create(title='جدید با اولویت پایین',assigned_user=self.user,priority='low',due_date=timezone.localdate()+timedelta(days=1))
        Task.objects.filter(pk=self.old.pk).update(created_at=timezone.now()-timedelta(days=2))
        for task in (self.old,self.new):
            TaskEvent.objects.create(task=task,to_status='follow_up',report_user=self.user,report_required=True)

    def rows(self,view,**params):
        response=self.client.get(reverse('hr:task_inbox'),{'view':view,**params})
        self.assertEqual(response.status_code,200)
        return response.json()

    def test_sorting_date_range_and_clear_defaults_match_in_all_three_tabs(self):
        day=jdatetime.date.fromgregorian(date=timezone.localdate()).strftime('%Y/%m/%d')
        for view in ('work','reports','updates'):
            with self.subTest(view=view):
                self.assertEqual([row['task'] for row in self.rows(view)['items']],[self.new.pk,self.old.pk])
                self.assertEqual([row['task'] for row in self.rows(view,sort='priority')['items']],[self.old.pk,self.new.pk])
                self.assertEqual([row['task'] for row in self.rows(view,sort='oldest')['items']],[self.old.pk,self.new.pk])
                self.assertEqual([row['task'] for row in self.rows(view,date_from=day,date_to=day)['items']],[self.new.pk])
                self.assertEqual([row['task'] for row in self.rows(view,date_basis='due',date_from=day,date_to=day)['items']],[self.old.pk])
                invalid=self.rows(view,date_from='اشتباه')
                self.assertIn('date_from',invalid['filter_errors']);self.assertEqual(invalid['items'],[])
                self.assertEqual(self.rows(view)['pagination']['total'],2)
