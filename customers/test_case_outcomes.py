from django.contrib.auth.models import User,Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import UserPermissionOverride
from accounts.permissions import ROLE_TO_GROUP
from customers.models import Customer,Reception,CustomerCase,CaseWorkSession
from calls.models import Call
from hr.models import Task,TaskEvent
from hr.task_access import visible_tasks


class CaseOutcomeTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_superuser('outcome_admin')
        self.sales=User.objects.create_user('outcome_sales')
        self.sales.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['sales'])[0])
        self.client.force_login(self.admin)
        self.person=Customer.objects.create(name='مشتری نتیجه مراجعه',mobile='09127778831',assigned_to=self.admin)
        self.rec=Reception.objects.create(customer=self.person,person_type='customer',referred_at=timezone.now(),referred_to=self.admin,registration_completed_at=timezone.now())

    def data(self,**changes):
        values=dict(reception=self.rec.pk,condition='cash',job='private',credit_rank='A1',quantity=1,visit_result='abandoned',cancel_reason='price',result_notes='مبلغ کالا نیاز به مذاکره دارد',sales_owner=self.sales.pk)
        values.update(changes);return values

    def save(self,**changes):
        return self.client.post(reverse('customers:case_save'),self.data(**changes))

    def test_abandoned_routes_card_and_one_automatic_followup_to_selected_sales_with_context(self):
        self.assertEqual(self.save().status_code,302)
        task=Task.objects.get(source_key=f'case_followup:{self.rec.pk}')
        self.assertEqual(task.assigned_user,self.sales);self.assertEqual(task.status,'follow_up')
        self.assertIsNone(task.due_date)
        self.assertIn('مبلغ کالا',task.description);self.assertIn('نیاز به مذاکره',task.description)
        self.person.refresh_from_db();self.assertEqual(self.person.assigned_to,self.sales)
        self.assertIn(task,visible_tasks(self.sales))
        self.assertEqual(Task.objects.get(source_key=f'case:{self.rec.pk}').status,'done')
        self.assertEqual(self.save().status_code,302)
        self.assertEqual(Task.objects.filter(source_key=task.source_key).count(),1)

    def test_abandoned_requires_reason_and_notes_and_rejects_non_sales_or_denied_owner(self):
        for changes in [dict(cancel_reason=''),dict(result_notes=''),dict(sales_owner=self.admin.pk)]:
            self.assertEqual(self.save(**changes).status_code,400)
        self.assertFalse(CustomerCase.objects.exists());self.assertFalse(CaseWorkSession.objects.exists())
        UserPermissionOverride.objects.create(user=self.sales,permission_key='hr.view_tasks',granted=False)
        self.assertEqual(self.save().status_code,400)
        self.assertFalse(Task.objects.filter(source_type='case_followup').exists())

    def test_review_notes_saved_without_cancellation_fields_or_sales_transfer(self):
        self.assertEqual(self.save(visit_result='review',sales_owner='').status_code,302)
        case=CustomerCase.objects.get(customer=self.person)
        self.assertEqual(case.result_notes,'مبلغ کالا نیاز به مذاکره دارد');self.assertEqual(case.cancel_reason,'')
        self.person.refresh_from_db();self.assertEqual(self.person.assigned_to,self.admin)
        self.assertFalse(Task.objects.filter(source_type='case_followup').exists())

    def test_no_followup_before_sales_assignment_and_permission_denial_cannot_be_bypassed(self):
        self.assertEqual(self.save(sales_owner='').status_code,302)
        self.assertFalse(Task.objects.filter(source_type='case_followup').exists())
        UserPermissionOverride.objects.create(user=self.admin,permission_key='customers.case_refer',granted=False)
        # A superuser intentionally bypasses overrides; exercise a non-supervisor card owner.
        support=User.objects.create_user('outcome_support')
        support.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['support'])[0])
        for key in ('customers.case','customers.case_edit'):
            UserPermissionOverride.objects.create(user=support,permission_key=key,granted=True)
        self.person.assigned_to=support;self.person.save(update_fields=['assigned_to'])
        self.client.force_login(support)
        self.assertEqual(self.save().status_code,400)
        self.assertFalse(Task.objects.filter(source_type='case_followup').exists())

    def test_real_followup_completion_finishes_task_but_old_completed_call_edit_does_not(self):
        self.person.needs_followup=True;self.person.save(update_fields=['needs_followup'])
        old=Call.objects.create(customer=self.person,caller_name=self.person.name,call_number=self.person.mobile,status='answered',is_followed_up=True,notes='تماس قدیمی')
        self.save();task=Task.objects.get(source_type='case_followup')
        old.notes='ویرایش یادداشت قبلی';old.save(update_fields=['notes'])
        task.refresh_from_db();self.assertEqual(task.status,'follow_up')
        Call.objects.create(customer=self.person,caller_name=self.person.name,call_number=self.person.mobile,status='answered',is_followed_up=True,notes='ثبت نتیجه پیگیری',called_by=self.sales)
        task.refresh_from_db();self.assertEqual(task.status,'done');self.assertIsNotNone(task.completed_at)
        self.save();task.refresh_from_db();self.assertEqual(task.status,'done')
        self.assertFalse(Task.objects.filter(source_type='customer_followup',status='follow_up').exists())

    def test_changing_result_withdraws_open_followup_and_keeps_visit_snapshot(self):
        self.save();task=Task.objects.get(source_type='case_followup')
        self.assertEqual(self.save(visit_result='review',sales_owner='',cancel_reason='',result_notes='بررسی مجدد شرایط').status_code,302)
        task.refresh_from_db();self.assertEqual(task.status,'cancelled')
        self.rec.refresh_from_db();self.assertEqual(self.rec.case_result,'review')
        self.assertEqual(self.rec.case_result_notes,'بررسی مجدد شرایط')

    def test_missing_case_handoff_is_repaired_on_inbox_without_starting_work_or_old_reports(self):
        Task.objects.filter(source_key=f'case:{self.rec.pk}').delete()
        response=self.client.get(reverse('hr:task_inbox'))
        task=Task.objects.get(source_key=f'case:{self.rec.pk}')
        self.assertEqual(task.status,'pending');self.assertEqual(task.assigned_user,self.admin)
        self.assertFalse(CaseWorkSession.objects.exists())
        self.assertIn(task.pk,[item['task'] for item in response.json()['items']])
        self.assertFalse(TaskEvent.objects.filter(task=task,report_required=True).exists())
        self.client.get(reverse('hr:task_inbox'))
        self.assertEqual(Task.objects.filter(source_key=task.source_key).count(),1)

    def test_registration_submit_hands_off_pending_case_and_newest_task_leads_inbox(self):
        self.rec.registration_completed_at=None;self.rec.save(update_fields=['registration_completed_at'])
        url=reverse('customers:registration_form',args=[self.rec.pk])
        data=dict(name=self.person.name,mobile=self.person.mobile,source='direct',stage='lead',notes='ثبت اطلاعات')
        response=self.client.post(url,data,follow=True)
        self.assertEqual(response.status_code,200)
        task=Task.objects.get(source_key=f'case:{self.rec.pk}')
        self.assertEqual(task.status,'pending');self.assertFalse(CaseWorkSession.objects.exists())
        self.assertNotContains(response,'id="case-editor"')
        data=self.client.get(reverse('hr:task_inbox')).json()
        self.assertEqual(data['items'][0]['task'],task.pk)
        self.assertEqual(data['items'][0]['stage_status'],'در انتظار تکمیل پرونده')

    def test_reactivated_automatic_task_rises_above_tasks_created_while_it_was_closed(self):
        task=Task.objects.get(source_key=f'case:{self.rec.pk}')
        task.status='cancelled';task.save()
        newer=Task.objects.create(title='کار جدید دیگر',assigned_user=self.admin)
        self.client.get(reverse('hr:task_inbox'))
        task.refresh_from_db();self.assertIsNotNone(task.queued_at)
        data=self.client.get(reverse('hr:task_inbox')).json()
        self.assertEqual(data['items'][0]['task'],task.pk)
        stamp=task.queued_at
        task.description='اصلاح توضیح';task.save()
        task.refresh_from_db();self.assertEqual(task.queued_at,stamp)

    def test_visit_outcomes_do_not_carry_over_to_a_new_visit(self):
        self.save()
        next_visit=Reception.objects.create(customer=self.person,person_type='customer',referred_at=timezone.now(),referred_to=self.admin,registration_completed_at=timezone.now())
        page=self.client.get(reverse('customers:hub'),{'tab':'case','r':next_visit.pk})
        for field in ('visit_result','cancel_reason','result_notes'):
            self.assertEqual(page.context['case_form'][field].value(),'')
        CustomerCase.objects.filter(customer=self.person).update(visit_result='review',result_notes='نتیجه مراجعه دیگر')
        old=self.client.get(reverse('customers:hub'),{'tab':'case','r':self.rec.pk})
        self.assertEqual(old.context['case_form']['visit_result'].value(),'abandoned')
        self.assertEqual(old.context['case_form']['cancel_reason'].value(),'price')
        self.assertFalse(Task.objects.filter(source_key=f'case_followup:{next_visit.pk}').exists())

    def test_clearing_referral_withdraws_task_without_losing_original_cancellation_context(self):
        self.save();task=Task.objects.get(source_type='case_followup');description=task.description
        self.assertEqual(self.save(sales_owner='').status_code,302)
        task.refresh_from_db();self.assertEqual(task.status,'cancelled')
        self.assertEqual(task.description,description)
        self.rec.refresh_from_db();self.assertIsNone(self.rec.case_followup_owner_id)

    def test_referral_only_edit_is_recorded_and_reassigns_followup(self):
        self.save()
        second=User.objects.create_user('outcome_second_sales')
        second.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['sales'])[0])
        self.assertEqual(self.save(sales_owner=second.pk).status_code,302)
        self.rec.refresh_from_db();self.assertEqual(self.rec.case_last_edited_by,self.admin)
        self.assertEqual(self.rec.case_followup_owner,second)
        task=Task.objects.get(source_type='case_followup')
        self.assertEqual(task.assigned_user,second);self.assertIsNotNone(task.queued_at)
