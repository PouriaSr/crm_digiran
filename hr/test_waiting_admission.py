from django.contrib.auth.models import User,Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.permissions import ROLE_TO_GROUP
from customers.models import Customer,Reception
from hr.models import Task,TaskNotice,TaskEvent
from hr.task_access import visible_tasks
from hr.task_automation import backfill


class WaitingAdmissionTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_superuser('waiting_admin')
        self.support=self.user('waiting_support','support')
        self.reception=self.user('waiting_reception','secretary')

    def user(self,name,role):
        user=User.objects.create_user(name)
        user.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP[role])[0])
        return user

    def test_status_waiting_itself_creates_task_without_reassignment(self):
        person=Customer.objects.create(name='در انتظار پذیرش',mobile='09125550001',is_interviewer=True,assigned_to=self.admin)
        task=Task.objects.get(source_type='admission',source_customer=person)
        self.assertEqual(task.status,'pending')
        self.assertEqual(task.assigned_user,self.admin)
        self.assertTrue(TaskNotice.objects.filter(task=task,user=self.admin,read_at=None).exists())
        self.assertFalse(person.receptions.exists())

    def test_registration_routes_to_reception_without_changing_card_owner(self):
        self.client.force_login(self.support)
        response=self.client.post(reverse('customers:hub_submit_call'),{'name':'کارجوی منتظر','mobile':'09125550002','is_interviewer':'on'})
        self.assertEqual(response.status_code,302)
        person=Customer.objects.get(mobile='09125550002')
        task=Task.objects.get(source_type='admission',source_customer=person)
        self.assertEqual(person.assigned_to,self.support)
        self.assertEqual(task.assigned_user,self.reception)
        self.assertTrue(visible_tasks(self.reception).filter(pk=task.pk).exists())
        self.assertFalse(visible_tasks(self.support).filter(pk=task.pk).exists())
        self.client.force_login(self.reception)
        feed=self.client.get(reverse('hr:task_inbox')).json()
        row=next(row for row in feed['items'] if row['task']==task.pk)
        self.assertTrue(row['can_act'])
        self.assertEqual(self.client.get(row['action_url']).status_code,200)
        self.client.post(reverse('customers:reception_action'),{'action':'arrive','customer':person.pk,'person_type':'interviewer'})
        task.refresh_from_db();self.assertEqual(task.status,'done')
        self.assertEqual(task.assigned_user,self.reception)
        self.assertEqual(task.events.get(to_status='done').report_user,self.reception)

    def test_backfill_matches_waiting_state_for_existing_candidates(self):
        Customer.objects.bulk_create([
            Customer(name='منتظر اول',mobile='09125550003',is_interviewer=True,assigned_to=self.admin),
            Customer(name='منتظر دوم',mobile='09125550004',is_interviewer=True,assigned_to=self.support),
            Customer(name='غیرفعال',mobile='09125550005',is_interviewer=True,is_deleted=True,assigned_to=self.support),
            Customer(name='مشتری بدون مراجعه',mobile='09125550006',assigned_to=self.support),
        ])
        backfill()
        count=(Task.objects.count(),TaskNotice.objects.count(),TaskEvent.objects.count())
        backfill()
        self.assertEqual((Task.objects.count(),TaskNotice.objects.count(),TaskEvent.objects.count()),count)
        waiting=set(Customer.objects.filter(is_interviewer=True,receptions__isnull=True).values_list('pk',flat=True))
        covered=set(Task.objects.filter(source_type='admission',status='pending').values_list('source_customer_id',flat=True))
        self.assertEqual(covered,waiting)
        self.assertFalse(TaskEvent.objects.filter(report_required=True).exists())

    def test_no_receiver_keeps_task_in_unassigned_queue_then_assigns_when_available(self):
        User.objects.filter(pk__in=[self.admin.pk,self.reception.pk]).update(is_active=False)
        person=Customer.objects.create(name='منتظر مسئول',mobile='09125550007',is_interviewer=True,assigned_to=self.support)
        task=Task.objects.get(source_type='admission',source_customer=person)
        self.assertEqual(task.status,'pending');self.assertIsNone(task.assigned_user)
        self.assertFalse(task.notices.exists())
        User.objects.filter(pk=self.reception.pk).update(is_active=True)
        backfill();backfill()
        task.refresh_from_db();self.assertEqual(task.assigned_user,self.reception)
        self.assertEqual(task.notices.filter(user=self.reception,read_at=None).count(),1)
        self.assertEqual(Task.objects.filter(source_type='admission',source_customer=person).count(),1)

    def test_archived_sales_visit_does_not_count_as_candidate_admission(self):
        Customer.objects.bulk_create([Customer(name='کارجو با سابقه مشتری',mobile='09125550008',is_interviewer=True,assigned_to=self.support)])
        person=Customer.objects.get(mobile='09125550008')
        Reception.objects.bulk_create([Reception(customer=person,person_type='customer',workflow_version=1)])
        backfill();backfill()
        task=Task.objects.get(source_type='admission',source_customer=person)
        self.assertEqual(task.status,'pending')
        self.assertEqual(task.assigned_user,self.reception)
        self.assertEqual(person.receptions.count(),1)
        self.assertFalse(person.receptions.filter(person_type='interviewer').exists())
