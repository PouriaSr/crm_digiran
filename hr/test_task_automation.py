from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import UserPermissionOverride
from accounts.permissions import ROLE_TO_GROUP, has_permission
from customers.models import Customer, FollowUp, Reception
from hr.models import Task, TaskEvent, TaskReport, TaskNotice, Employee, LeaveRequest
from hr.task_access import visible_tasks
from hr.task_automation import backfill


class TaskAutomationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('automation_admin')
        self.owner = self.user('automation_owner', 'support')
        self.other = self.user('automation_other', 'support')
        self.customer = Customer.objects.create(name='مشتری گردش کار', mobile='09123456789', assigned_to=self.owner)

    def user(self, name, role):
        user = User.objects.create_user(name)
        user.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP[role])[0])
        return user

    def followup(self):
        fu = FollowUp.objects.create(customer=self.customer, due_date=timezone.localdate()+timedelta(days=1), created_by=self.owner)
        return fu, Task.objects.get(source_key='followup:'+str(fu.pk))

    def finish(self, fu, actor=None):
        with patch('hr.task_automation.get_current_user', return_value=actor or self.owner):
            fu.is_done=True;fu.done_at=timezone.now();fu.save()

    def test_every_role_including_secretary_and_accountant_has_own_task_access(self):
        for role in ROLE_TO_GROUP:
            user = self.user('role_'+role, role)
            self.assertTrue(has_permission(user,'hr.view_tasks'), role)
            self.assertTrue(has_permission(user,'hr.report_tasks'), role)

    def test_followup_creation_and_repeated_save_do_not_duplicate_task(self):
        fu, task = self.followup()
        self.assertEqual(task.assigned_user,self.owner)
        self.assertEqual(task.status,'follow_up')
        fu.save();fu.save()
        self.assertEqual(Task.objects.filter(source_key=task.source_key).count(),1)
        self.assertEqual(TaskNotice.objects.filter(task=task,user=self.owner).count(),1)
        self.assertFalse(task.events.exists())

    def test_real_source_completion_requests_report_from_actual_actor(self):
        fu, task = self.followup();self.finish(fu,self.admin)
        task.refresh_from_db();self.assertEqual(task.status,'done')
        event=task.events.get();self.assertTrue(event.report_required);self.assertEqual(event.report_user,self.admin)
        self.client.force_login(self.admin)
        feed=self.client.get(reverse('hr:task_inbox')).json()
        self.assertEqual(feed['reports'][0]['event'],event.pk)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('hr:task_inbox')).json()['reports'],[])

    def test_cannot_finish_source_task_by_reporting_without_operation(self):
        fu, task=self.followup();self.client.force_login(self.owner)
        response=self.client.post(reverse('hr:task_report',args=[task.pk]),{'text':'توضیح کافی'})
        self.assertEqual(response.status_code,409)
        task.refresh_from_db();self.assertEqual(task.status,'follow_up');self.assertFalse(TaskReport.objects.exists())

    def test_report_idempotence_validation_and_authorization(self):
        fu, task=self.followup();self.finish(fu);event=task.events.get()
        self.client.force_login(self.other)
        url=reverse('hr:task_report',args=[task.pk])
        self.assertEqual(self.client.post(url,{'event':event.pk,'text':'گزارش دیگری'}).status_code,404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(url,{'event':event.pk,'text':' '}).status_code,400)
        self.assertEqual(self.client.post(url,{'event':event.pk,'text':'گزارش ثبت اول'}).status_code,200)
        self.assertTrue(self.client.post(url,{'event':event.pk,'text':'متن دوباره'}).json()['already_saved'])
        self.assertEqual(TaskReport.objects.get().text,'گزارش ثبت اول')
        self.assertEqual(self.client.get(reverse('hr:task_inbox')).json()['pending_reports'],0)

    def test_reassignment_moves_open_task_and_notice_without_duplicate(self):
        fu, task=self.followup();self.customer.assigned_to=self.other;self.customer.save()
        task.refresh_from_db();self.assertEqual(task.assigned_user,self.other)
        self.assertEqual(Task.objects.filter(source_key=task.source_key).count(),1)
        self.assertFalse(visible_tasks(self.owner).filter(pk=task.pk).exists())
        self.assertTrue(TaskNotice.objects.filter(task=task,user=self.other,read_at=None).exists())
        self.assertFalse(TaskNotice.objects.filter(task=task,user=self.owner,read_at=None).exists())

    def test_deleted_customer_cancels_task_and_hides_pending_reports(self):
        fu,task=self.followup();self.customer.is_deleted=True;self.customer.save()
        task.refresh_from_db();self.assertEqual(task.status,'cancelled')
        self.assertFalse(task.events.filter(report_required=True).exists())
        self.assertFalse(visible_tasks(self.admin).filter(pk=task.pk).exists())

    def test_case_completion_creates_registration_and_finishes_case(self):
        rec=Reception.objects.create(customer=self.customer,person_type='customer',referred_at=timezone.now(),referred_to=self.admin)
        task=Task.objects.get(source_key='case:'+str(rec.pk));self.assertEqual(task.assigned_user,self.admin)
        with patch('hr.task_automation.get_current_user',return_value=self.admin):
            rec.case_completed_at=timezone.now();rec.case_completed_by=self.admin;rec.save()
        task.refresh_from_db();self.assertEqual(task.status,'done')
        self.assertEqual(Task.objects.get(source_key='registration:'+str(rec.pk)).status,'pending')
        self.assertTrue(task.events.get().report_required)

    def test_existing_database_backfill_is_idempotent_and_does_not_invent_past_reports(self):
        FollowUp.objects.bulk_create([FollowUp(customer=self.customer,due_date=timezone.localdate(),created_by=self.owner),FollowUp(customer=self.customer,due_date=timezone.localdate(),created_by=self.owner,is_done=True)])
        legacy=Task.objects.create(title='کار قبلی تمام شده',status='done',assigned_user=self.owner)
        before=legacy.completed_at
        call_command('sync_workflow_tasks',verbosity=0);call_command('sync_workflow_tasks',verbosity=0)
        self.assertEqual(Task.objects.filter(source_type='followup').count(),1)
        self.assertFalse(TaskEvent.objects.filter(report_required=True).exists())
        legacy.refresh_from_db();self.assertEqual(legacy.completed_at,before)

    def test_manual_task_without_employee_can_be_finished_with_only_report(self):
        task=Task.objects.create(title='وظیفه دستی',assigned_user=self.owner)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('hr:task_detail',args=[task.pk])).status_code,200)
        response=self.client.post(reverse('hr:task_report',args=[task.pk]),{'text':'انجام شد و بررسی کردم'})
        self.assertEqual(response.status_code,200)
        task.refresh_from_db();self.assertEqual(task.status,'done');self.assertIsNotNone(task.completed_at)
        self.assertEqual(TaskReport.objects.get().author,self.owner)

    def test_advanced_denial_blocks_reporting(self):
        fu,task=self.followup();self.finish(fu);event=task.events.get()
        UserPermissionOverride.objects.create(user=self.owner,permission_key='hr.report_tasks',granted=False)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse('hr:task_report',args=[task.pk]),{'event':event.pk,'text':'گزارش معتبر'}).status_code,403)
        self.assertFalse(TaskReport.objects.exists())

    def test_other_user_cannot_mark_notice_as_read(self):
        fu,task=self.followup();notice=task.notices.get(user=self.owner)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('hr:task_notice_read'),{'notice':notice.pk}).status_code,404)
        notice.refresh_from_db();self.assertIsNone(notice.read_at)

    def test_source_tasks_cannot_be_changed_or_deleted_from_manual_task_controls(self):
        fu,task=self.followup();self.client.force_login(self.admin)
        for name,data in [('task_toggle',{'status':'done'}),('task_delete',{}),('task_edit',{'title':'تغییر'})]:
            response=self.client.post(reverse('hr:'+name,args=[task.pk]),data)
            self.assertEqual(response.status_code,302)
            self.assertTrue(Task.objects.filter(pk=task.pk,status='follow_up').exists())

    def test_invoice_status_tracks_real_issue_and_payment(self):
        from sales.models import Invoice
        invoice=Invoice.objects.create(number='AUTO-001',customer=self.customer,created_by=self.admin)
        task=Task.objects.get(source_key='invoice:'+str(invoice.pk))
        with patch('hr.task_automation.get_current_user',return_value=self.admin):
            invoice.status='issued';invoice.save();invoice.status='paid';invoice.save()
        task.refresh_from_db();self.assertEqual(task.status,'done')
        self.assertEqual(list(task.events.order_by('pk').values_list('to_status',flat=True)),['follow_up','done'])

    def test_followup_does_not_leave_duplicate_active_call_task(self):
        from calls.models import Call
        call=Call.objects.create(caller_name='مشتری',call_number='09123456789',customer=self.customer,status='followup',follow_up_date=timezone.localdate(),called_by=self.owner)
        old=Task.objects.get(source_key='call:'+str(call.pk))
        fu=FollowUp.objects.create(customer=self.customer,due_date=timezone.localdate(),created_by=self.owner)
        old.refresh_from_db();self.assertEqual(old.status,'cancelled')
        self.assertEqual(Task.objects.filter(source_customer=self.customer).exclude(status__in=['done','cancelled']).count(),1)

    def test_existing_members_task_denials_are_enabled_once_without_changing_other_permissions(self):
        import importlib
        from django.apps import apps
        from django.db import connection
        denied=UserPermissionOverride.objects.create(user=self.owner,permission_key='hr.view_tasks',granted=False)
        other=UserPermissionOverride.objects.create(user=self.owner,permission_key='customers.hiring',granted=False)
        migration=importlib.import_module('hr.migrations.0009_enable_personal_tasks')
        migration.enable_members(apps,type('Editor',(),{'connection':connection})())
        denied.refresh_from_db();other.refresh_from_db()
        self.assertTrue(denied.granted);self.assertFalse(other.granted)

    def test_report_context_is_preserved_when_task_description_changes(self):
        fu, task=self.followup();self.finish(fu)
        event=task.events.get();original=event.snapshot.copy()
        task.description='شرح فعلی متفاوت';task.save()
        event.refresh_from_db();self.assertEqual(event.snapshot,original)

    def test_legacy_followup_flag_without_appointment_is_included(self):
        Customer.objects.filter(pk=self.customer.pk).update(needs_followup=True)
        backfill();backfill()
        task=Task.objects.get(source_type='customer_followup')
        self.assertEqual(task.assigned_user,self.owner)
        with self.captureOnCommitCallbacks(execute=True), patch('hr.task_automation.get_current_user',return_value=self.owner):
            self.customer.needs_followup=False;self.customer.save()
        task.refresh_from_db();self.assertEqual(task.status,'done')
        self.assertTrue(task.events.get().report_required)

    def test_dated_followup_replaces_undated_flag_task_without_two_active_tasks(self):
        Customer.objects.filter(pk=self.customer.pk).update(needs_followup=True)
        backfill()
        old=Task.objects.get(source_type='customer_followup')
        self.followup()
        old.refresh_from_db();self.assertEqual(old.status,'cancelled')
        self.assertEqual(Task.objects.exclude(status__in=['done','cancelled']).count(),1)

    def test_actual_performer_can_report_without_global_task_management(self):
        manager=self.user('performing_manager','sales_manager')
        UserPermissionOverride.objects.create(user=manager,permission_key='hr.manage_tasks',granted=False)
        fu,task=self.followup();self.finish(fu,manager)
        event=task.events.get()
        self.client.force_login(manager)
        self.assertEqual(self.client.get(reverse('hr:task_inbox')).json()['pending_reports'],1)
        self.assertEqual(self.client.post(reverse('hr:task_report',args=[task.pk]),{'event':event.pk,'text':'گزارش انجام توسط مدیر'}).status_code,200)

    def test_admin_cannot_override_or_delete_automatic_source_task(self):
        from django.contrib import admin
        from django.test import RequestFactory
        from hr.admin import TaskAdmin
        fu,task=self.followup()
        request=RequestFactory().get('/admin/hr/task/');request.user=self.admin
        controller=TaskAdmin(Task,admin.site)
        self.assertIn('status',controller.get_readonly_fields(request,task))
        self.assertFalse(controller.has_delete_permission(request,task))
        self.assertNotIn('delete_selected',controller.get_actions(request))
