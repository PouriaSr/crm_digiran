from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from hr.models import Task,TaskEvent


class StageFilterTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_superuser('filters_new_order')
        self.other=User.objects.create_superuser('filters_other')
        self.client.force_login(self.user)
        self.registration=Task.objects.create(title='ثبت اطلاعات',source_type='registration',source_key='filter:registration',assigned_user=self.user,priority='urgent')
        self.case=Task.objects.create(title='پرونده',source_type='case',source_key='filter:case',assigned_user=self.user,priority='low',status='in_progress')
        Task.objects.create(title='فاکتور دیگری',source_type='invoice',source_key='filter:foreign-invoice',assigned_user=self.other)
        Task.objects.create(title='کار دیگری',source_type='registration',source_key='filter:other',assigned_user=self.other)

    def test_personal_filters_work_in_all_views_with_workflow_order(self):
        for task in (self.registration,self.case):TaskEvent.objects.create(task=task,report_user=self.user,report_required=True,to_status='follow_up',snapshot={})
        for view in ('work','reports','updates'):
            with self.subTest(view=view):
                data=self.client.get(reverse('hr:task_inbox'),{'view':view,'sort':'workflow'}).json()
                self.assertEqual([item['task'] for item in data['items']],[self.registration.pk,self.case.pk])
                data=self.client.get(reverse('hr:task_inbox'),{'view':view,'source':'registration','priority':'urgent','status':'pending'}).json()
                self.assertEqual([item['task'] for item in data['items']],[self.registration.pk])
                sources=[key for key,label in data['filter_choices']['source']]
                self.assertLess(sources.index('registration'),sources.index('case'))
                self.assertNotIn('invoice',sources)

    def test_full_personal_and_team_lists_share_source_filter_and_order(self):
        for scope,count in [('mine',1),('',2)]:
            page=self.client.get(reverse('hr:task_list'),{'scope':scope,'source':'registration','due':'undated','sort':'workflow'})
            self.assertEqual(page.status_code,200)
            self.assertEqual(page.context['page_obj'].paginator.count,count)
            self.assertNotContains(page,'name="employee"')
        data=self.client.get(reverse('hr:task_inbox'),{'source':'not-valid'}).json()
        self.assertIn('source',data['filter_errors']);self.assertEqual(data['items'],[])
