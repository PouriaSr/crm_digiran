from datetime import timedelta
from django.contrib.auth.models import User, Group
from django.test import TestCase
from django.utils import timezone
from accounts.models import UserPermissionOverride
from accounts.permissions import ROLE_TO_GROUP
from customers.models import Customer, Reception, HiringApplication, InterviewSession, FollowUp
from hr.models import Task, TaskNotice, TaskEvent
from hr.task_access import visible_tasks, source_url
from hr.task_automation import backfill


class WorkflowCoverageTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_superuser('coverage_admin')
        self.secretary=User.objects.create_user('coverage_secretary')
        self.secretary.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['secretary'])[0])
        self.person=Customer.objects.create(name='فرد تست',mobile='09126663344',assigned_to=self.admin)

    def application(self, legacy=False):
        self.person.is_interviewer=True;self.person.save()
        rec=Reception.objects.create(customer=self.person,person_type='interviewer',workflow_version=1 if legacy else 2,
            referred_at=None if legacy else timezone.now(),referred_to=self.admin)
        return HiringApplication.objects.create(reception=rec)

    def session(self,app,**kwargs):
        return InterviewSession.objects.create(application=app,round_number=1,kind='first',**kwargs)

    def test_arrival_assigns_secretary_and_referral_closes_task(self):
        rec=Reception.objects.create(customer=self.person,person_type='customer',created_by=self.secretary,arrived_at=timezone.now())
        task=Task.objects.get(source_key=f'reception:{rec.pk}')
        self.assertEqual(task.assigned_user,self.secretary)
        self.assertTrue(visible_tasks(self.secretary).filter(pk=task.pk).exists())
        self.assertIn('tab=reception',source_url(task))
        self.assertTrue(TaskNotice.objects.filter(task=task,user=self.secretary,read_at=None).exists())
        rec.referred_at=timezone.now();rec.referred_to=self.admin;rec.save()
        task.refresh_from_db();self.assertEqual(task.status,'done')
        self.assertTrue(Task.objects.filter(source_key=f'case:{rec.pk}',status='pending').exists())

    def test_repeat_tracks_model_saves_and_never_creates_from_unsaved_draft(self):
        app=self.application()
        first=self.session(app,result='repeat',next_interview_at=timezone.now()+timedelta(days=1))
        self.assertFalse(Task.objects.filter(hiring_session=first).exists())
        first.saved_at=timezone.now();first.ended_at=first.saved_at;first.save()
        task=Task.objects.get(hiring_session=first)
        next_session=InterviewSession.objects.create(application=app,round_number=2,kind='repeat',result='repeat',next_interview_at=first.next_interview_at)
        task.refresh_from_db();self.assertEqual(task.status,'in_progress')
        self.assertEqual(task.performed_session,next_session)
        self.assertFalse(Task.objects.filter(hiring_session=next_session).exists())
        next_session.result='accepted';next_session.saved_at=timezone.now();next_session.ended_at=next_session.saved_at;next_session.save()
        task.refresh_from_db();self.assertEqual(task.status,'done')
        finished=task.completed_at;notices=TaskNotice.objects.count()
        backfill();backfill()
        task.refresh_from_db();self.assertEqual(task.completed_at,finished)
        self.assertEqual(TaskNotice.objects.count(),notices)

    def test_invitation_has_appointment_and_finishes_on_recorded_result(self):
        app=self.application()
        session=self.session(app,result='accepted',saved_at=timezone.now(),invite=True,will_attend='yes',invitation_at=timezone.now()+timedelta(days=2))
        task=Task.objects.get(source_key=f'invitation:{session.pk}')
        self.assertEqual(task.status,'follow_up');self.assertIsNotNone(task.due_date)
        self.assertIn('tab=hiring',source_url(task))
        session.collaboration='pending_docs';session.save()
        task.refresh_from_db();self.assertEqual(task.status,'done')
        self.assertTrue(task.events.filter(report_required=True,to_status='done').exists())

    def test_backfill_covers_legacy_hiring_and_bulk_completed_sources_quietly(self):
        app=self.application(legacy=True)
        Task.objects.filter(source_key=f'interview:{app.pk}').delete()
        first=self.session(app,saved_at=timezone.now(),result='repeat',next_interview_at=timezone.now()+timedelta(days=1))
        Task.objects.filter(hiring_session=first).delete()
        fu=FollowUp.objects.create(customer=Customer.objects.create(name='مشتری',mobile='09126663345',assigned_to=self.admin),due_date=timezone.localdate())
        FollowUp.objects.filter(pk=fu.pk).update(is_done=True)
        TaskEvent.objects.all().delete()
        backfill();backfill()
        self.assertEqual(Task.objects.filter(hiring_session=first).count(),1)
        self.assertEqual(Task.objects.get(source_key=f'followup:{fu.pk}').status,'done')
        self.assertFalse(TaskEvent.objects.filter(report_required=True).exists())

    def test_assignment_requires_view_and_edit_and_deleted_candidate_cancels(self):
        UserPermissionOverride.objects.create(user=self.secretary,permission_key='customers.case',granted=True)
        UserPermissionOverride.objects.create(user=self.secretary,permission_key='customers.case_edit',granted=False)
        self.person.assigned_to=self.secretary;self.person.save()
        rec=Reception.objects.create(customer=self.person,person_type='customer',referred_at=timezone.now(),referred_to=self.admin)
        self.assertEqual(Task.objects.get(source_key=f'case:{rec.pk}').assigned_user,self.admin)
        rec.delete()
        self.person.assigned_to=self.admin;self.person.save()
        app=self.application()
        first=self.session(app,saved_at=timezone.now(),result='repeat',next_interview_at=timezone.now()+timedelta(days=1))
        completed=Task.objects.get(source_key=f'interview:{app.pk}')
        completed_at=completed.completed_at
        self.person.is_deleted=True;self.person.save()
        self.assertEqual(Task.objects.get(hiring_session=first).status,'cancelled')
        backfill()
        completed.refresh_from_db()
        self.assertEqual(completed.status,'done')
        self.assertEqual(completed.completed_at,completed_at)

    def test_restored_assignment_gets_new_notice(self):
        fu=FollowUp.objects.create(customer=self.person,due_date=timezone.localdate())
        task=Task.objects.get(source_key=f'followup:{fu.pk}')
        self.person.is_deleted=True;self.person.save()
        self.assertFalse(task.notices.filter(read_at=None).exists())
        self.person.is_deleted=False;self.person.save()
        task.refresh_from_db();self.assertEqual(task.status,'follow_up')
        self.assertTrue(task.notices.filter(user=self.admin,read_at=None).exists())

    def test_legacy_followup_call_without_date_still_creates_one_task(self):
        from calls.models import Call
        from hr.task_automation import sync_customer_flag
        standalone=Call.objects.create(caller_name='تماس قدیمی',call_number='09126663347',status='followup',called_by=self.admin)
        self.assertEqual(Task.objects.get(source_key=f'call:{standalone.pk}').status,'follow_up')
        self.person.needs_followup=True;self.person.save()
        sync_customer_flag(self.person)
        old=Task.objects.get(source_key=f'customer-followup:{self.person.pk}')
        call=Call.objects.create(customer=self.person,caller_name=self.person.name,call_number=self.person.mobile,status='followup',called_by=self.admin)
        old.refresh_from_db();self.assertEqual(old.status,'cancelled')
        self.assertEqual(Task.objects.filter(source_customer=self.person).exclude(source_type='admission').exclude(status__in=['done','cancelled']).count(),1)
        self.assertTrue(Task.objects.filter(source_key=f'call:{call.pk}',due_date=None).exists())


from django.db import transaction
from django.test import TransactionTestCase


class WorkflowPermissionRefreshTests(TransactionTestCase):
    def test_permission_and_account_changes_reassign_without_duplicate_tasks(self):
        admin=User.objects.create_superuser('refresh_admin')
        user=User.objects.create_user('refresh_support')
        user.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['support'])[0])
        person=Customer.objects.create(name='مشتری',mobile='09126663346',assigned_to=user)
        fu=FollowUp.objects.create(customer=person,due_date=timezone.localdate())
        task=Task.objects.get(source_key=f'followup:{fu.pk}')
        self.assertEqual(task.assigned_user,user)
        with transaction.atomic():
            override=UserPermissionOverride.objects.create(user=user,permission_key='hr.view_tasks',granted=False)
            UserPermissionOverride.objects.create(user=user,permission_key='customers.case_edit',granted=False)
        task.refresh_from_db();self.assertEqual(task.assigned_user,admin)
        override.delete()
        task.refresh_from_db();self.assertEqual(task.assigned_user,user)
        user.is_active=False;user.save()
        task.refresh_from_db();self.assertEqual(task.assigned_user,admin)
        self.assertEqual(Task.objects.filter(source_key=task.source_key).count(),1)
        self.assertFalse(TaskNotice.objects.filter(task=task,user=user,read_at=None).exists())
        self.assertTrue(TaskNotice.objects.filter(task=task,user=admin,read_at=None).exists())
