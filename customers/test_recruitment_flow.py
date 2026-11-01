from datetime import timedelta
import tempfile
from unittest.mock import patch

import jdatetime
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserPermissionOverride
from accounts.permissions import has_permission
from crm.private_files import HiringDocumentStorage
from customers.models import (CaseWorkSession, Customer, HiringAd, HiringApplication,
                              HiringReferral, InterviewSession, Reception)


def jday(value):
    return jdatetime.date.fromgregorian(date=value.date()).strftime('%Y/%m/%d')


class NewRecruitmentFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('recruitment_admin', password='test-only')
        cls.manager = User.objects.create_user('recruitment_manager')
        cls.manager.groups.add(Group.objects.get_or_create(name='مدیر فروش')[0])
        cls.secretary = User.objects.create_user('recruitment_secretary')
        cls.secretary.groups.add(Group.objects.get_or_create(name='منشی')[0])
        cls.outsider = User.objects.create_user('recruitment_other')
        cls.outsider.groups.add(Group.objects.get_or_create(name='کارشناس فروش')[0])
        UserPermissionOverride.objects.create(user=cls.outsider, permission_key='customers.hiring', granted=True)
        UserPermissionOverride.objects.create(user=cls.outsider, permission_key='customers.hiring_documents', granted=True)
        cls.customer = Customer.objects.create(name='کارجوی آزمایشی', mobile='09125556677', assigned_to=cls.manager)
        cls.ad = HiringAd.objects.create(platform='jobvision', number=1000, role_key='role:sales', role_title='کارشناس فروش', created_by=cls.admin)

    def setUp(self):
        self.client.force_login(self.admin)
        self.now = timezone.now().replace(microsecond=0)

    def arrive(self, person='interviewer', resume=None):
        data = {'action':'arrive', 'person_type':person, 'customer':self.customer.pk, 'job_ad':self.ad.pk}
        if resume:
            data['resume'] = resume
        with patch('django.utils.timezone.now', return_value=self.now):
            response = self.client.post(reverse('customers:reception_action'), data)
        self.assertEqual(response.status_code, 302)
        return Reception.objects.get(customer=self.customer)

    def refer(self, rec):
        with patch('django.utils.timezone.now', return_value=self.now + timedelta(minutes=1)):
            response = self.client.post(reverse('customers:reception_action'), {'action':'refer', 'reception':rec.pk, 'user':self.manager.pk})
        self.assertEqual(response.status_code, 302)
        rec.refresh_from_db()

    def start(self, rec, kind='first', offset=3):
        with patch('django.utils.timezone.now', return_value=self.now + timedelta(minutes=offset)):
            response = self.client.post(reverse('customers:interview_open', args=[rec.pk]), {'kind':kind})
        self.assertEqual(response.status_code, 200, response.content[:300])
        return InterviewSession.objects.filter(application__reception=rec).latest('pk')

    def assessment(self, **extra):
        return {'job_ad':self.ad.pk, 'national_id':'1234567891', 'behavior':'friendly', 'fit':'high', 'seriousness':'high', 'questions':'technical', 'grade':'A', 'result':'accepted', 'proposed_role':'role:sales', 'experience':'related', **extra}

    def test_customer_arrival_only_records_arrival_and_case_open_starts_wait(self):
        rec = self.arrive('customer')
        self.assertEqual(rec.arrived_at, self.now)
        self.assertIsNone(rec.wait_started_at)
        self.assertFalse(rec.is_waiting)
        self.refer(rec)
        url = reverse('customers:case_open', args=[rec.pk])
        with patch('django.utils.timezone.now', return_value=self.now + timedelta(minutes=2)):
            first = self.client.post(url)
        self.assertEqual(first.status_code, 200)
        with patch('django.utils.timezone.now', return_value=self.now + timedelta(minutes=3)):
            again = self.client.post(url)
        self.assertEqual(first.json()['id'], again.json()['id'])
        work = CaseWorkSession.objects.get(reception=rec)
        self.assertEqual(work.started_at, self.now + timedelta(minutes=2))
        valid = {'reception':rec.pk, 'work_session':work.pk, 'condition':'retired', 'job':'retired', 'credit_rank':'A2', 'quantity':1, 'visit_result':'review'}
        with patch('django.utils.timezone.now', return_value=self.now + timedelta(minutes=5)):
            result = self.client.post(reverse('customers:case_save'), valid)
        self.assertEqual(result.status_code, 302, result.content[:300])
        work.refresh_from_db()
        self.assertEqual(work.seconds, 180)
        self.client.get(reverse('customers:hub'), {'tab':'case','r':rec.pk})
        self.assertEqual(CaseWorkSession.objects.count(), 1)
        with patch('django.utils.timezone.now', return_value=self.now + timedelta(minutes=6)):
            self.client.post(url)
        self.assertEqual(CaseWorkSession.objects.count(), 2)

    def test_interviewer_wait_ends_on_open_and_session_time_ends_on_end_button(self):
        rec = self.arrive()
        self.refer(rec)
        self.assertTrue(rec.is_waiting)
        self.assertIsNone(rec.wait_ended_at)
        session = self.start(rec)
        self.assertEqual(session.waiting_seconds, 180)
        rec.refresh_from_db()
        self.assertEqual(rec.wait_ended_at, session.started_at)
        self.assertFalse(rec.is_waiting)
        same = self.start(rec, offset=4)
        self.assertEqual(session.pk, same.pk)
        with patch('django.utils.timezone.now', return_value=self.now + timedelta(minutes=6)):
            self.client.post(reverse('customers:interview_end', args=[session.pk]))
        with patch('django.utils.timezone.now', return_value=self.now + timedelta(minutes=8)):
            result = self.client.post(reverse('customers:interview_save', args=[session.pk]), self.assessment())
        self.assertEqual(result.status_code, 302)
        session.refresh_from_db()
        self.assertEqual(session.seconds, 180)
        self.assertEqual(session.application.status, 'interviewed')
        self.assertEqual(session.proposed_role_title, 'کارشناس فروش')

    def test_save_without_end_button_stops_timer_and_invalid_form_does_not(self):
        rec = self.arrive(); self.refer(rec); session = self.start(rec)
        response = self.client.post(reverse('customers:interview_save', args=[session.pk]), {'result':'rejected'})
        self.assertEqual(response.status_code, 400)
        session.refresh_from_db(); self.assertIsNone(session.ended_at)
        with patch('django.utils.timezone.now', return_value=self.now + timedelta(minutes=5)):
            response = self.client.post(reverse('customers:interview_save', args=[session.pk]), self.assessment(result='rejected', rejection_reason='skills'))
        self.assertEqual(response.status_code, 302)
        session.refresh_from_db(); self.assertEqual(session.seconds, 120)
        self.assertEqual(session.application.status, 'rejected')
        denied = self.client.post(reverse('customers:interview_open', args=[rec.pk]), {'kind':'repeat'})
        self.assertEqual(denied.status_code, 409)
        self.assertEqual(InterviewSession.objects.count(), 1)

    def test_repeat_prefills_previous_assessment_and_keeps_round_history(self):
        rec=self.arrive();self.refer(rec);first=self.start(rec)
        data=self.assessment(result='repeat', next_date=jday(self.now+timedelta(days=1)), next_time='14:30')
        result=self.client.post(reverse('customers:interview_save', args=[first.pk]),data)
        self.assertEqual(result.status_code,302)
        second=self.start(rec,'repeat',offset=10)
        self.assertEqual(second.round_number,2)
        self.assertEqual(second.behavior,first.behavior or 'friendly')
        self.assertEqual(second.grade,'A')
        self.assertEqual(second.waiting_seconds,180)
        self.assertEqual(InterviewSession.objects.filter(saved_at__isnull=False).count(),1)

    def test_invitation_records_owner_and_does_not_create_an_account(self):
        rec=self.arrive();self.refer(rec);session=self.start(rec)
        count=User.objects.count()
        data=self.assessment(invite='on',will_attend='yes',invitation_date=jday(self.now+timedelta(days=1)),invitation_time='۱۴:۳۰',collaboration='pending_docs',invited_by=self.outsider.pk)
        response=self.client.post(reverse('customers:interview_save',args=[session.pk]),data)
        self.assertEqual(response.status_code,302)
        session.refresh_from_db()
        self.assertEqual(session.application.status,'invited')
        self.assertEqual(session.invited_by_id,self.manager.pk)
        self.assertEqual(timezone.localtime(session.invitation_at).strftime('%H:%M'),'14:30')
        self.assertEqual(User.objects.count(),count)

    def test_permissions_and_owner_are_enforced_on_every_operation(self):
        rec=self.arrive();self.refer(rec)
        self.client.force_login(self.outsider)
        response=self.client.post(reverse('customers:interview_open',args=[rec.pk]))
        self.assertEqual(response.status_code,404)
        self.assertFalse(InterviewSession.objects.exists())
        self.client.force_login(self.manager)
        UserPermissionOverride.objects.create(user=self.manager,permission_key='customers.hiring_interview',granted=False)
        response=self.client.post(reverse('customers:interview_open',args=[rec.pk]))
        self.assertEqual(response.status_code,403)
        self.assertFalse(InterviewSession.objects.exists())
        self.assertTrue(has_permission(self.secretary,'customers.reception_add'))
        self.assertFalse(has_permission(self.secretary,'customers.hiring_interview'))

    def test_referral_creates_no_timer_or_interview(self):
        rec=self.arrive();self.refer(rec)
        response=self.client.post(reverse('customers:hiring_refer',args=[rec.pk]),{'user':self.admin.pk,'note':'ارجاع به مسئول دیگر'})
        self.assertEqual(response.status_code,302)
        self.assertFalse(InterviewSession.objects.exists())
        self.assertFalse(CaseWorkSession.objects.exists())
        self.assertEqual(HiringReferral.objects.count(),1)
        self.customer.refresh_from_db();self.assertEqual(self.customer.assigned_to_id,self.admin.pk)

    def test_ad_numbers_increment_independently_per_platform(self):
        for platform,start in HiringAd.STARTS.items():
            expected=start+1 if platform=='jobvision' else start
            for number in (expected,expected+1):
                response=self.client.post(reverse('customers:hiring_ad_create'),{'platform':platform,'role_key':'role:sales','email':''})
                self.assertEqual(response.status_code,302)
                self.assertTrue(HiringAd.objects.filter(platform=platform,number=number).exists())

    def test_resume_is_validated_private_and_owner_authorized(self):
        with tempfile.TemporaryDirectory() as folder, override_settings(HIRING_PRIVATE_ROOT=folder):
            with patch.object(HiringApplication._meta.get_field('resume'),'storage',HiringDocumentStorage()):
                resume=SimpleUploadedFile('رزومه.pdf',b'%PDF-1.4\nprivate test resume',content_type='application/pdf')
                rec=self.arrive(resume=resume);self.refer(rec)
                application=HiringApplication.objects.get(reception=rec)
                self.assertTrue(application.resume.storage.exists(application.resume.name))
                with self.assertRaises(ValueError):_ = application.resume.url
                response=self.client.get(reverse('customers:hiring_resume',args=[rec.pk]));self.assertEqual(response.status_code,200)
                self.assertEqual(b''.join(response.streaming_content),b'%PDF-1.4\nprivate test resume');response.close()
                self.client.force_login(self.outsider)
                self.assertEqual(self.client.get(reverse('customers:hiring_resume',args=[rec.pk])).status_code,404)

    def test_invalid_resume_does_not_register_arrival(self):
        fake=SimpleUploadedFile('fake.pdf',b'<script>bad</script>',content_type='application/pdf')
        response=self.client.post(reverse('customers:reception_action'),{'action':'arrive','person_type':'interviewer','customer':self.customer.pk,'resume':fake})
        self.assertEqual(response.status_code,400)
        self.assertFalse(Reception.objects.filter(customer=self.customer).exists())

    def test_hiring_filters_keep_scope_and_reject_invalid_dates(self):
        rec=self.arrive();self.refer(rec)
        response=self.client.get(reverse('customers:hub'),{'tab':'hiring','hiring_status':'arrived','hiring_owner':self.manager.pk,'hiring_from':jday(self.now),'hiring_to':jday(self.now)})
        self.assertEqual(response.status_code,200)
        self.assertEqual(list(response.context['hiring_records']),[rec])
        response=self.client.get(reverse('customers:hub'),{'tab':'hiring','hiring_from':'تاریخ اشتباه'})
        self.assertTrue(response.context['hiring_filters'].errors)
        self.assertEqual(response.context['hiring_records'].paginator.count,0)

    def test_national_id_instant_save_does_not_end_interview(self):
        rec=self.arrive();self.refer(rec);session=self.start(rec)
        result=self.client.post(reverse('customers:hiring_identity',args=[rec.pk]),{'national_id':'۱۲۳۴۵۶۷۸۹۱'})
        self.assertEqual(result.status_code,200)
        self.customer.refresh_from_db();self.assertEqual(self.customer.national_id,'1234567891')
        session.refresh_from_db();self.assertIsNone(session.ended_at)

    def test_invalid_case_save_keeps_clock_and_stale_tab_cannot_finish_new_round(self):
        rec=self.arrive('customer');self.refer(rec)
        work=self.client.post(reverse('customers:case_open',args=[rec.pk])).json()['id']
        data={'reception':rec.pk,'work_session':work,'condition':'cash','job':'private','credit_rank':'A1','quantity':1,'visit_result':'review'}
        invalid=self.client.post(reverse('customers:case_save'),dict(data,job=''))
        self.assertEqual(invalid.status_code,400)
        self.assertIsNone(CaseWorkSession.objects.get(pk=work).ended_at)
        self.assertEqual(self.client.post(reverse('customers:case_save'),data).status_code,302)
        newer=self.client.post(reverse('customers:case_open',args=[rec.pk])).json()['id']
        self.assertNotEqual(work,newer)
        self.assertEqual(self.client.post(reverse('customers:case_save'),data).status_code,409)
        self.assertIsNone(CaseWorkSession.objects.get(pk=newer).ended_at)

    def test_new_permissions_apply_to_existing_users_and_preserve_denials(self):
        from accounts.forms import UserEditForm
        from accounts.permissions import get_user_permissions
        self.assertTrue(has_permission(self.manager,'customers.hiring_interview'))
        for key in ('hiring_interview','hiring_refer','hiring_ads','hiring_documents'):
            self.assertIn('perm__customers_'+key,UserEditForm(instance=self.manager).fields)
        UserPermissionOverride.objects.create(user=self.manager,permission_key='customers.hiring',granted=False)
        denied=get_user_permissions(User.objects.get(pk=self.manager.pk))
        self.assertNotIn('customers.hiring',denied)
        self.assertNotIn('customers.hiring_interview',denied)
        self.assertNotIn('customers.hiring_refer',denied)
        self.assertNotIn('customers.hiring_ads',denied)
        # Identity access is inherited separately and still requires hiring at the URL.
        rec=self.arrive();self.refer(rec) if has_permission(self.manager,'customers.hiring') else None
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse('customers:hiring_resume',args=[rec.pk])).status_code,403)

    def test_fresh_repeat_arrival_starts_new_wait_without_overwriting_first_visit(self):
        rec=self.arrive();self.refer(rec);session=self.start(rec)
        with patch('django.utils.timezone.now',return_value=self.now+timedelta(minutes=5)):
            self.client.post(reverse('customers:interview_save',args=[session.pk]),self.assessment(result='repeat',next_date=jday(self.now+timedelta(days=1)),next_time='۱۰:۳۰'))
        next_arrival=self.now+timedelta(days=1)
        with patch('django.utils.timezone.now',return_value=next_arrival):
            self.client.post(reverse('customers:reception_action'),{'action':'arrive','customer':self.customer.pk,'person_type':'interviewer'})
        rec.refresh_from_db();application=HiringApplication.objects.get(reception=rec)
        self.assertEqual(rec.arrived_at,self.now)
        self.assertEqual(application.current_arrived_at,next_arrival)
        self.assertTrue(rec.is_waiting)
        with patch('django.utils.timezone.now',return_value=next_arrival+timedelta(minutes=7)):
            self.client.post(reverse('customers:interview_open',args=[rec.pk]),{'kind':'repeat'})
        latest=application.sessions.latest('pk')
        self.assertEqual(latest.waiting_seconds,420)
        self.assertEqual(latest.arrived_at,next_arrival)
        session.refresh_from_db();self.assertEqual(session.waiting_seconds,180)

    def test_clock_endpoints_only_expose_owned_timestamps(self):
        rec=self.arrive();self.refer(rec);session=self.start(rec)
        self.client.force_login(self.outsider)
        response=self.client.get(reverse('customers:interview_clock'),{'ids':[session.pk]})
        self.assertEqual(response.json()['sessions'],[])
        response=self.client.get(reverse('customers:hiring_clock'),{'ids':[rec.pk]})
        self.assertEqual(response.json()['states'],[])
        self.client.force_login(self.manager)
        response=self.client.get(reverse('customers:interview_clock'),{'ids':[session.pk]})
        self.assertEqual(set(response.json()['sessions'][0]),{'pk','started_at','ended_at'})
        self.assertIn('no-store',response['Cache-Control'])

    def test_editing_last_result_preserves_all_timestamps_and_prior_rounds(self):
        rec=self.arrive();self.refer(rec);session=self.start(rec)
        self.client.post(reverse('customers:interview_save',args=[session.pk]),self.assessment())
        session.refresh_from_db();times=(session.started_at,session.ended_at,session.saved_at)
        result=self.client.post(reverse('customers:interview_edit',args=[session.pk]),self.assessment(grade='B',notes='ویرایش ارزیابی'))
        self.assertEqual(result.status_code,302)
        session.refresh_from_db();self.assertEqual(times,(session.started_at,session.ended_at,session.saved_at))
        self.assertEqual(session.grade,'B')
        self.assertEqual(InterviewSession.objects.count(),1)

    def test_conditional_fields_and_jalali_filters_are_validated(self):
        rec=self.arrive();self.refer(rec);session=self.start(rec)
        for data in [self.assessment(result='rejected',rejection_reason=''),self.assessment(result='repeat',next_date='۱۴۰۵/۱۳/۰۱',next_time='۲۵:۰۰'),self.assessment(experience=''),self.assessment(invite='on',will_attend='yes',invitation_date='',invitation_time='')]:
            self.assertEqual(self.client.post(reverse('customers:interview_save',args=[session.pk]),data).status_code,400)
        session.refresh_from_db();self.assertIsNone(session.ended_at)
        response=self.client.get(reverse('customers:hub'),{'tab':'reception','workflow_from':jday(self.now),'workflow_to':jday(self.now),'workflow_owner':self.manager.pk})
        self.assertEqual(list(response.context['reception_records']),[rec])
        response=self.client.get(reverse('customers:hub'),{'tab':'reception','workflow_from':'۱۴۰۵/۱۳/۰۱'})
        self.assertTrue(response.context['workflow_filters'].errors)

    def test_repeat_action_is_visible_disabled_until_valid_repeat_result_then_enabled(self):
        from html.parser import HTMLParser
        def repeat_buttons(content):
            class Buttons(HTMLParser):
                def __init__(self):
                    super().__init__();self.current=None;self.text='';self.items=[]
                def handle_starttag(self,tag,attrs):
                    if tag=='button':self.current=dict(attrs);self.text=''
                def handle_data(self,data):
                    if self.current is not None:self.text+=data
                def handle_endtag(self,tag):
                    if tag=='button' and self.current is not None:
                        if self.text.strip() in ('مصاحبه مجدد', 'تسک مصاحبه مجدد'):self.items.append(self.current)
                        self.current=None
            parser=Buttons();parser.feed(content.decode());return parser.items
        rec=self.arrive();self.refer(rec)
        page=self.client.get(reverse('customers:hub'),{'tab':'hiring','r':rec.pk})
        buttons=repeat_buttons(page.content)
        self.assertTrue(buttons)
        self.assertTrue(all(('disabled' in button) for button in buttons))
        session=self.start(rec)
        denied=self.client.post(reverse('customers:interview_open',args=[rec.pk]),{'kind':'repeat'})
        self.assertEqual(denied.status_code,409)
        self.assertEqual(InterviewSession.objects.count(),1)
        invalid=self.client.post(reverse('customers:interview_save',args=[session.pk]),self.assessment(result='repeat',next_date='',next_time=''))
        self.assertEqual(invalid.status_code,400)
        self.assertContains(invalid,'data-form-error-summary',status_code=400)
        session.refresh_from_db();self.assertIsNone(session.saved_at)
        data=self.assessment(result='repeat',next_date=jday(self.now+timedelta(days=1)),next_time='۱۰:۳۰')
        self.assertEqual(self.client.post(reverse('customers:interview_save',args=[session.pk]),data).status_code,302)
        page=self.client.get(reverse('customers:hub'),{'tab':'hiring','r':rec.pk})
        buttons=repeat_buttons(page.content)
        self.assertTrue(buttons)
        self.assertTrue(all(not ('disabled' in button) and button['data-open-hiring']==reverse('customers:hiring_task',args=[rec.pk]) for button in buttons))
        self.start(rec,'repeat',offset=10)
        page=self.client.get(reverse('customers:hub'),{'tab':'hiring','r':rec.pk})
        self.assertContains(page,'تسک در حال انجام')
        self.assertNotContains(page,'>ویرایش جلسه</button>')

    def test_previous_saved_session_cannot_be_edited_during_repeat_session(self):
        rec=self.arrive();self.refer(rec);first=self.start(rec)
        data=self.assessment(result='repeat',next_date=jday(self.now+timedelta(days=1)),next_time='10:30')
        self.client.post(reverse('customers:interview_save',args=[first.pk]),data)
        self.start(rec,'repeat',offset=10)
        edit=reverse('customers:interview_edit',args=[first.pk])
        self.assertEqual(self.client.get(edit).status_code,409)
        self.assertEqual(self.client.post(edit,self.assessment(result='accepted')).status_code,409)
        first.refresh_from_db();self.assertEqual(first.result,'repeat')
        self.assertEqual(first.application.status,'repeat')

    def test_repeat_arrival_during_open_interview_does_not_restart_wait(self):
        rec=self.arrive();self.refer(rec);first=self.start(rec)
        data=self.assessment(result='repeat',next_date=jday(self.now+timedelta(days=1)),next_time='10:30')
        self.client.post(reverse('customers:interview_save',args=[first.pk]),data)
        second=self.start(rec,'repeat',offset=10)
        rec.refresh_from_db();before=(rec.wait_started_at,rec.wait_ended_at,rec.hiring.current_arrived_at)
        with patch('django.utils.timezone.now',return_value=self.now+timedelta(days=1)):
            self.client.post(reverse('customers:reception_action'),{'action':'arrive','customer':self.customer.pk,'person_type':'interviewer'})
        rec.refresh_from_db();self.assertEqual(before,(rec.wait_started_at,rec.wait_ended_at,rec.hiring.current_arrived_at))
        self.assertFalse(rec.is_waiting)
        self.assertEqual(InterviewSession.objects.filter(saved_at__isnull=True).get().pk,second.pk)

    def test_migrated_running_wait_finishes_when_interview_starts_or_resumes(self):
        rec=self.arrive();self.refer(rec)
        Reception.objects.filter(pk=rec.pk).update(timing_version=2)
        session=self.start(rec)
        rec.refresh_from_db();self.assertFalse(rec.is_waiting)
        self.assertEqual(rec.wait_ended_at,session.started_at)
        # An already-open session from an older release is repaired at its own
        # start time rather than now; its original timing and assessment remain.
        Reception.objects.filter(pk=rec.pk).update(is_waiting=True,wait_ended_at=None)
        again=self.start(rec,offset=20)
        rec.refresh_from_db();self.assertEqual(again.pk,session.pk)
        self.assertEqual(rec.wait_ended_at,session.started_at)
        self.assertFalse(rec.is_waiting)

    def schedule_repeat(self):
        rec=self.arrive();self.refer(rec);source=self.start(rec)
        data=self.assessment(result='repeat',next_date=jday(self.now+timedelta(days=1)),next_time='۱۰:۳۰')
        response=self.client.post(reverse('customers:interview_save',args=[source.pk]),data)
        self.assertEqual(response.status_code,302)
        source.refresh_from_db()
        from hr.models import Task
        return rec,source,Task.objects.get(hiring_session=source)

    def test_repeat_task_lifecycle_and_short_scheduling_popup(self):
        from hr.models import Employee,Task
        rec,source,task=self.schedule_repeat()
        self.assertEqual(task.status,'pending')
        self.assertEqual(task.assigned_user_id,self.manager.pk)
        self.assertIsNone(task.assigned_to_id)
        self.assertEqual(Employee.objects.count(),0)
        self.assertEqual(task.due_time.strftime('%H:%M'),'10:30')
        url=reverse('customers:hiring_task',args=[rec.pk])
        response=self.client.get(url,HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(response,'تغییر موعد تسک')
        self.assertNotContains(response,'name="national_id"')
        self.assertNotContains(response,'name="behavior"')
        self.assertEqual(InterviewSession.objects.count(),1)
        self.assertEqual(self.client.post(url,{'next_date':jday(self.now+timedelta(days=2)),'next_time':'۱۲:۱۵'}).status_code,302)
        task.refresh_from_db();source.refresh_from_db()
        self.assertEqual(task.due_time.strftime('%H:%M'),'12:15')
        self.assertEqual(task.due_date,timezone.localtime(source.next_interview_at).date())
        self.assertEqual(Task.objects.count(),1)
        second=self.start(rec,'repeat',offset=10)
        task.refresh_from_db();self.assertEqual(task.status,'in_progress')
        self.assertEqual(task.performed_session_id,second.pk)
        self.assertEqual(self.client.post(url,{'next_date':jday(self.now),'next_time':'11:00'}).status_code,409)
        data=self.assessment(result='accepted');data.pop('national_id')
        response=self.client.post(reverse('customers:interview_save',args=[second.pk]),data)
        self.assertEqual(response.status_code,302)
        task.refresh_from_db();self.assertEqual(task.status,'done')
        self.assertIsNotNone(task.completed_at)
        source.refresh_from_db();self.assertEqual(source.result,'repeat')
        self.assertEqual(Task.objects.count(),1)
        # Double submission cannot create a task or change the completed appointment.
        self.client.post(reverse('customers:interview_save',args=[second.pk]),data)
        self.assertEqual(Task.objects.count(),1)
        page=self.client.get(reverse('customers:hub'),{'tab':'hiring','r':rec.pk})
        self.assertContains(page,'id="repeat-task"')

    def test_repeat_task_edits_cancel_reactivate_and_referral_reassigns(self):
        from hr.models import Task
        rec,source,task=self.schedule_repeat()
        edit=reverse('customers:interview_edit',args=[source.pk])
        self.assertEqual(self.client.post(edit,self.assessment()).status_code,302)
        task.refresh_from_db();self.assertEqual(task.status,'cancelled')
        data=self.assessment(result='repeat',next_date=jday(self.now+timedelta(days=3)),next_time='13:45')
        self.assertEqual(self.client.post(edit,data).status_code,302)
        task.refresh_from_db();self.assertEqual(task.status,'pending')
        self.assertEqual(task.due_time.strftime('%H:%M'),'13:45')
        self.assertEqual(Task.objects.count(),1)
        response=self.client.post(reverse('customers:hiring_refer',args=[rec.pk]),{'user':self.outsider.pk})
        self.assertEqual(response.status_code,302)
        task.refresh_from_db();self.assertEqual(task.assigned_user_id,self.outsider.pk)

    def test_repeat_task_permissions_visibility_and_due_time(self):
        from hr.task_access import visible_tasks,overdue_condition
        from hr.models import Task
        rec,source,task=self.schedule_repeat()
        self.client.force_login(self.outsider)
        url=reverse('customers:hiring_task',args=[rec.pk])
        self.assertEqual(self.client.get(url,HTTP_X_REQUESTED_WITH='XMLHttpRequest').status_code,404)
        self.assertFalse(visible_tasks(self.outsider).filter(pk=task.pk).exists())
        self.assertTrue(visible_tasks(self.manager).filter(pk=task.pk).exists())
        now=timezone.localtime(self.now)
        task.due_date=now.date();task.due_time=(now-timedelta(minutes=1)).time().replace(tzinfo=None);task.save()
        with patch('django.utils.timezone.now',return_value=self.now):
            self.assertTrue(task.is_overdue)
            self.assertTrue(Task.objects.filter(overdue_condition(),pk=task.pk).exists())
        self.client.force_login(self.admin)
        page=self.client.get(reverse('customers:hub'),{'tab':'hiring','hiring_task_status':'overdue'})
        self.assertEqual(list(page.context['hiring_records']),[rec])
        UserPermissionOverride.objects.create(user=self.manager,permission_key='customers.hiring',granted=False)
        self.assertFalse(visible_tasks(self.manager).filter(pk=task.pk).exists())

    def test_task_read_access_without_interview_write_permission(self):
        rec,source,task=self.schedule_repeat()
        UserPermissionOverride.objects.create(user=self.manager,permission_key='customers.hiring_interview',granted=False)
        self.client.force_login(self.manager)
        url=reverse('customers:hiring_task',args=[rec.pk])
        response=self.client.get(url,HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(response,'موعد جلسه')
        self.assertNotContains(response,'name="next_date"')
        self.assertNotContains(response,'data-kind="repeat"')
        self.assertEqual(self.client.post(url,{'next_date':jday(self.now),'next_time':'10:00'}).status_code,403)
        task.refresh_from_db();self.assertEqual(task.status,'pending')

    def test_task_filters_notifications_and_no_generic_edit_of_hiring_task(self):
        from accounts.notifications import get_notifications
        from hr.forms import TaskForm
        rec,source,task=self.schedule_repeat()
        self.assertTrue(TaskForm().fields['assigned_to'].required)
        now=timezone.localtime(self.now)
        task.due_date=now.date();task.due_time=(now-timedelta(minutes=1)).time().replace(tzinfo=None);task.save()
        with patch('django.utils.timezone.now',return_value=self.now):
            self.assertTrue(any('وظیفه عقب‌افتاده' in n['title'] for n in get_notifications(self.admin)))
            response=self.client.get(reverse('hr:task_list'),{'due':'overdue','responsible':self.manager.pk})
            self.assertEqual(list(response.context['page_obj']),[task])
        response=self.client.post(reverse('hr:task_edit',args=[task.pk]),{'title':'نباید ذخیره شود'})
        self.assertRedirects(response,reverse('customers:hiring_task',args=[rec.pk]),fetch_redirect_response=False)
        task.refresh_from_db();self.assertNotEqual(task.title,'نباید ذخیره شود')

    def test_incompatible_repeat_and_invitation_cannot_create_task(self):
        rec=self.arrive();self.refer(rec);source=self.start(rec)
        data=self.assessment(result='repeat',next_date=jday(self.now+timedelta(days=1)),next_time='11:00',invite='on',will_attend='yes',invitation_date=jday(self.now+timedelta(days=2)),invitation_time='12:00')
        response=self.client.post(reverse('customers:interview_save',args=[source.pk]),data)
        self.assertContains(response,'دعوت به همکاری فقط برای نتیجه قبول',status_code=400)
        from hr.models import Task
        self.assertFalse(Task.objects.filter(hiring_session=source).exists())
        source.refresh_from_db();self.assertIsNone(source.saved_at)
