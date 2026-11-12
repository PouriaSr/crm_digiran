from datetime import timedelta,time
from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User,Group
from django.urls import reverse
from django.utils import timezone
from accounts.models import UserPermissionOverride
from accounts.permissions import ROLE_TO_GROUP
from customers.models import Customer,Reception,FollowUp
from calls.models import Call
from hr.models import Task
from hr.task_access import visible_tasks


class AutomaticRoutingRegressionTests(TestCase):
    def user(self,name,role):
        user=User.objects.create_user(name)
        user.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP[role])[0])
        return user

    def grant(self,user,**values):
        for key,value in values.items():UserPermissionOverride.objects.create(user=user,permission_key=key.replace('__','.'),granted=value)

    def test_case_does_not_go_to_previous_card_owner_who_cannot_open_the_card(self):
        manager=User.objects.create_superuser('routing_manager')
        owner=self.user('routing_current','support')
        previous=self.user('routing_previous','support')
        self.grant(owner,customers__registration=True,customers__case_edit=False)
        self.grant(previous,customers__case=True,customers__case_edit=True)
        person=Customer.objects.create(name='پرونده جدید',mobile='09127775501',assigned_to=owner)
        rec=Reception.objects.create(customer=person,person_type='customer',referred_at=timezone.now(),referred_to=previous,registration_completed_at=timezone.now())
        task=Task.objects.get(source_key=f'case:{rec.pk}')
        self.assertEqual(task.assigned_user,manager)
        self.assertTrue(visible_tasks(manager).filter(pk=task.pk).exists())
        self.assertFalse(visible_tasks(previous).filter(pk=task.pk).exists())

    def test_supervisor_can_receive_case_without_superuser_flag(self):
        manager=self.user('routing_role_admin','sales_manager')
        owner=self.user('routing_registered','support')
        self.grant(owner,customers__registration=True)
        person=Customer.objects.create(name='در انتظار پرونده',mobile='09127775502',assigned_to=owner)
        rec=Reception.objects.create(customer=person,person_type='customer',referred_at=timezone.now(),registration_completed_at=timezone.now())
        task=Task.objects.filter(source_key=f'case:{rec.pk}').first()
        self.assertIsNotNone(task)
        self.assertEqual(task.assigned_user,manager)
        self.client.force_login(manager)
        data=self.client.get(reverse('hr:task_inbox')).json()
        self.assertIn(task.pk,[item['task'] for item in data['items']])
        self.assertEqual(self.client.get(reverse('customers:hub'),{'tab':'case','r':rec.pk}).context['case_record'],rec)

    def test_waiting_case_remains_visible_as_unassigned_when_no_eligible_owner_exists(self):
        owner=self.user('routing_no_case','support')
        self.grant(owner,customers__registration=True)
        person=Customer.objects.create(name='پرونده بدون مسئول مجاز',mobile='09127775503',assigned_to=owner)
        rec=Reception.objects.create(customer=person,person_type='customer',referred_at=timezone.now(),registration_completed_at=timezone.now())
        task=Task.objects.filter(source_key=f'case:{rec.pk}').first()
        self.assertIsNotNone(task)
        self.assertEqual(task.status,'pending');self.assertIsNone(task.assigned_user)

    def test_finished_old_followup_does_not_swallow_new_call_on_same_day(self):
        admin=User.objects.create_superuser('routing_followup_admin')
        person=Customer.objects.create(name='پیگیری تازه',mobile='09127775504',assigned_to=admin)
        due=timezone.localdate()+timedelta(days=1)
        FollowUp.objects.create(customer=person,due_date=due,due_time=time(9),is_done=True)
        call=Call.objects.create(customer=person,caller_name=person.name,call_number=person.mobile,status='followup',called_by=admin,follow_up_date=due,follow_up_time=time(14))
        task=Task.objects.filter(source_key=f'call:{call.pk}',status='follow_up').first()
        self.assertIsNotNone(task)

    def test_referral_rollback_withdraws_downstream_work_without_marking_it_done(self):
        admin=User.objects.create_superuser('routing_rollback')
        person=Customer.objects.create(name='توقف ارجاع',mobile='09127775505',assigned_to=admin)
        rec=Reception.objects.create(customer=person,person_type='customer',referred_at=timezone.now(),registration_completed_at=timezone.now())
        task=Task.objects.get(source_key=f'case:{rec.pk}')
        rec.referred_at=None;rec.save(update_fields=['referred_at'])
        task.refresh_from_db();self.assertEqual(task.status,'cancelled')
        self.assertFalse(task.events.filter(report_required=True).exists())

    def test_repeat_interview_reassignment_checks_task_access_and_preserves_completed_owner(self):
        from customers.models import HiringApplication, InterviewSession
        from customers.recruitment_tasks import reassign_interview_tasks, sync_interview_task
        admin=User.objects.create_superuser('routing_repeat_admin')
        owner=self.user('routing_repeat_owner','support')
        self.grant(owner,customers__hiring=True,customers__hiring_interview=True,hr__view_tasks=False)
        person=Customer.objects.create(name='مصاحبه مجدد با محدودیت',mobile='09127775508',assigned_to=owner,is_interviewer=True)
        rec=Reception.objects.create(customer=person,person_type='interviewer',referred_at=timezone.now())
        app=HiringApplication.objects.create(reception=rec)
        first=InterviewSession.objects.create(application=app,round_number=1,kind='first',saved_at=timezone.now(),result='repeat',next_interview_at=timezone.now()+timedelta(days=1))
        task=sync_interview_task(first,admin)
        reassign_interview_tasks(app,owner)
        task.refresh_from_db();self.assertEqual(task.assigned_user,admin)
        InterviewSession.objects.create(application=app,round_number=2,kind='repeat',saved_at=timezone.now(),ended_at=timezone.now(),result='accepted')
        sync_interview_task(first,admin);task.refresh_from_db();self.assertEqual(task.status,'done')
        other=User.objects.create_superuser('routing_repeat_later_admin')
        person.assigned_to=other;person.save(update_fields=['assigned_to'])
        sync_interview_task(first,other);task.refresh_from_db();self.assertEqual(task.assigned_user,admin)

    def test_historical_registration_completion_time_and_owner_are_preserved(self):
        admin=User.objects.create_superuser('routing_history_admin')
        person=Customer.objects.create(name='سابقه مرحله',mobile='09127775507',assigned_to=admin)
        rec=Reception.objects.create(customer=person,person_type='customer',referred_at=timezone.now())
        completed=timezone.now()-timedelta(hours=2)
        rec.registration_completed_at=completed;rec.save(update_fields=['registration_completed_at'])
        task=Task.objects.get(source_key=f'registration:{rec.pk}')
        self.assertEqual(task.completed_at,completed)
        new_owner=self.user('routing_history_new','sales_manager')
        person.assigned_to=new_owner;person.save(update_fields=['assigned_to'])
        task.refresh_from_db();self.assertEqual(task.assigned_user,admin)
        self.assertEqual(task.completed_at,completed)
        self.assertEqual(Task.objects.get(source_key=f'case:{rec.pk}').assigned_user,new_owner)


class AutomaticPermissionRoutingTests(TransactionTestCase):
    user = AutomaticRoutingRegressionTests.user
    grant = AutomaticRoutingRegressionTests.grant

    def test_unassigned_case_is_flagged_to_manager_then_repaired_after_access_grant(self):
        manager=self.user('routing_access_manager','sales_manager')
        self.grant(manager,customers__case_edit=False)
        person=Customer.objects.create(name='اصلاح دسترسی',mobile='09127775506',assigned_to=manager)
        rec=Reception.objects.create(customer=person,person_type='customer',referred_at=timezone.now(),registration_completed_at=timezone.now())
        task=Task.objects.get(source_key=f'case:{rec.pk}')
        self.assertTrue(task.needs_assignment)
        self.client.force_login(manager)
        page=self.client.get(reverse('hr:task_list'),{'assignment':'unassigned'})
        self.assertIn(task,list(page.context['page_obj']));self.assertGreaterEqual(page.context['unassigned_count'],1)
        self.assertContains(page,'نیازمند تعیین مسئول')
        self.assertNotIn(task.pk,[row['task'] for row in self.client.get(reverse('hr:task_inbox')).json()['items']])
        override=UserPermissionOverride.objects.get(user=manager,permission_key='customers.case_edit')
        override.granted=True;override.save()
        task.refresh_from_db();self.assertEqual(task.assigned_user,manager)
        self.assertFalse(task.needs_assignment)
        self.assertEqual(Task.objects.filter(source_key=task.source_key).count(),1)
        data=self.client.get(reverse('hr:task_inbox'),{'source':'case'}).json()
        self.assertEqual(next(row for row in data['items'] if row['task']==task.pk)['stage_status'],'در انتظار تکمیل پرونده')
