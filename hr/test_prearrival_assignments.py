from datetime import timedelta
from django.contrib.auth.models import Group,User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import UserPermissionOverride
from accounts.permissions import ROLE_TO_GROUP
from customers.models import Customer,Reception,HiringApplication,InterviewSession
from hr.models import Task,TaskNotice,TaskEvent,TaskReport
from hr.task_automation import backfill
from hr.task_access import visible_tasks


class PrearrivalAssignmentTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_superuser('before_arrival_admin')
        self.first=self.user('reception_first','secretary')
        self.second=self.user('reception_second','secretary')
        self.operator=self.user('reception_operator','operator')
        self.person=Customer.objects.create(name='مراجعه پیش از ورود',mobile='09126664401',assigned_to=self.admin)
        self.client.force_login(self.admin)

    def user(self,name,role):
        user=User.objects.create_user(name)
        user.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP[role])[0])
        return user

    def assign(self,user=None,person=None):
        return self.client.post(reverse('customers:admission_assign',args=[(person or self.person).pk]),{'assigned_to':(user or self.first).pk})

    def test_generic_card_transfer_creates_visible_actionable_task_before_any_visit(self):
        response=self.client.post(reverse('customers:reassign',args=[self.person.pk]),{'assigned_to':self.first.pk})
        self.assertEqual(response.status_code,302)
        self.assertFalse(Reception.objects.filter(customer=self.person).exists())
        task=Task.objects.get(source_type='admission',source_customer=self.person)
        self.assertEqual(task.assigned_user,self.first)
        self.assertEqual(task.status,'pending')
        self.client.force_login(self.first)
        feed=self.client.get(reverse('hr:task_inbox')).json()
        row=next(row for row in feed['items'] if row['task']==task.pk)
        self.assertTrue(row['can_act'])
        self.assertIn('tab=reception',row['action_url'])
        self.assertIn('c='+str(self.person.pk),row['action_url'])
        self.assertTrue(TaskNotice.objects.filter(task=task,user=self.first,read_at=None).exists())
        response=self.client.get(row['action_url'])
        self.assertEqual(response.status_code,200)
        self.assertContains(response,f'value="{self.person.pk}" data-interviewer="no" selected')
        self.assertEqual(self.client.post(reverse('hr:task_report',args=[task.pk]),{'text':'بدون ورود'}).status_code,409)
        self.client.post(reverse('customers:reception_action'),{'action':'arrive','customer':self.person.pk,'person_type':'customer'})
        task.refresh_from_db();self.assertEqual(task.status,'done')
        event=task.events.get(to_status='done',report_required=True)
        self.assertEqual(event.report_user,self.first)
        self.assertEqual(self.client.post(reverse('hr:task_report',args=[task.pk]),{'event':event.pk,'text':'ورود واقعی ثبت شد'}).status_code,200)
        self.assertEqual(TaskReport.objects.get(event=event).author,self.first)
        self.assertTrue(Task.objects.filter(source_type='reception',source_customer=self.person,status='pending',assigned_user=self.first).exists())

    def test_candidate_has_independent_assignment_without_sales_or_fake_admission(self):
        self.person.is_interviewer=True;self.person.save()
        self.assertEqual(self.assign().status_code,302)
        self.assertFalse(Reception.objects.exists())
        task=Task.objects.get(source_type='admission',source_customer=self.person)
        self.assertTrue(visible_tasks(self.first).filter(pk=task.pk).exists())
        self.client.force_login(self.first)
        self.client.post(reverse('customers:reception_action'),{'action':'arrive','customer':self.person.pk,'person_type':'interviewer'})
        task.refresh_from_db();self.assertEqual(task.status,'done')
        self.assertEqual(Reception.objects.get().person_type,'interviewer')

    def test_forwarding_and_resynchronization_keep_one_task_and_move_notice(self):
        self.assign();self.assign();backfill();backfill()
        task=Task.objects.get(source_type='admission')
        self.assign(self.second)
        task.refresh_from_db();self.assertEqual(task.assigned_user,self.second)
        self.assertFalse(visible_tasks(self.first).filter(pk=task.pk).exists())
        self.assertFalse(task.notices.filter(user=self.first,read_at=None).exists())
        self.assertTrue(task.notices.filter(user=self.second,read_at=None).exists())
        self.assertEqual(Task.objects.filter(source_type='admission').count(),1)
        self.person.refresh_from_db();self.person.assigned_to=self.operator;self.person.save()
        task.refresh_from_db();self.assertEqual(task.status,'cancelled')
        self.assertFalse(Reception.objects.exists())

    def test_old_reception_assignments_backfill_without_duplicate_or_historical_reports(self):
        Customer.objects.filter(pk=self.person.pk).update(assigned_to=self.first)
        already=Customer.objects.create(name='وارد شده',mobile='09126664402',assigned_to=self.admin)
        Reception.objects.create(customer=already,person_type='customer',created_by=self.first,arrived_at=timezone.now())
        Customer.objects.filter(pk=already.pk).update(assigned_to=self.first)
        backfill();before=(Task.objects.count(),TaskNotice.objects.count(),TaskEvent.objects.count())
        backfill()
        self.assertEqual((Task.objects.count(),TaskNotice.objects.count(),TaskEvent.objects.count()),before)
        self.assertTrue(Task.objects.filter(source_type='admission',source_customer=self.person,assigned_user=self.first,status='pending').exists())
        self.assertFalse(Task.objects.filter(source_type='admission',source_customer=already).exists())
        self.assertFalse(TaskEvent.objects.filter(report_required=True).exists())

    def test_explicit_assignment_to_manager_and_denied_receiver(self):
        self.assertEqual(self.assign(self.admin).status_code,302)
        task=Task.objects.get(source_type='admission')
        self.assertEqual(task.assigned_user,self.admin)
        UserPermissionOverride.objects.create(user=self.first,permission_key='customers.reception_add',granted=False)
        response=self.assign(self.first)
        self.assertEqual(response.status_code,302)
        self.person.refresh_from_db();self.assertEqual(self.person.assigned_to,self.admin)
        self.assertEqual(Task.objects.filter(source_type='admission').count(),1)
        self.client.force_login(self.operator)
        self.assertEqual(self.assign(self.second).status_code,403)

    def test_repeat_visit_completes_prearrival_task_on_same_reception(self):
        self.person.is_interviewer=True;self.person.save()
        old=timezone.now()-timedelta(days=4)
        rec=Reception.objects.create(customer=self.person,person_type='interviewer',arrived_at=old,referred_at=old,referred_to=self.admin)
        app=HiringApplication.objects.create(reception=rec,current_arrived_at=old,status='repeat')
        session=InterviewSession.objects.create(application=app,round_number=1,kind='first',saved_at=old+timedelta(hours=1),result='repeat',next_interview_at=timezone.now())
        app.latest_session=session;app.save()
        self.assign()
        task=Task.objects.get(source_type='admission')
        self.client.force_login(self.first)
        self.client.post(reverse('customers:reception_action'),{'action':'arrive','customer':self.person.pk,'person_type':'interviewer'})
        task.refresh_from_db();self.assertEqual(task.status,'done')
        self.assertEqual(Reception.objects.filter(customer=self.person).count(),1)
