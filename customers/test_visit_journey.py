from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import User, Group
from django.template.loader import render_to_string
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone
from customers.models import Customer, Reception, HiringAd, HiringApplication, HiringReferral, InterviewSession


class VisitJourneyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('journey_admin')
        self.client.force_login(self.user)
        self.person = Customer.objects.create(name='مراجعه آزمایشی روند', mobile='09127776602', assigned_to=self.user)
        self.rec = Reception.objects.create(customer=self.person, person_type='customer', referred_at=timezone.now(), referred_to=self.user)
        self.now = timezone.now()

    def profile(self, **changes):
        return dict(name=self.person.name, mobile=self.person.mobile, source='direct', stage='lead', notes='یادداشت', address='تهران', **changes)

    def test_profile_first_last_save_and_actual_edit_are_separate(self):
        url = reverse('customers:registration_form', args=[self.rec.pk])
        for minutes, changes in [(0, {}), (1, {}), (2, {'email': 'new@example.com'})]:
            with patch('django.utils.timezone.now', return_value=self.now + timedelta(minutes=minutes)):
                self.assertEqual(self.client.post(url, self.profile(**changes)).status_code, 302)
            self.rec.refresh_from_db()
            self.assertEqual(self.rec.registration_completed_at, self.now)
            if minutes < 2:
                self.assertIsNone(self.rec.registration_last_edited_at)
        self.assertEqual(self.rec.registration_last_saved_at, self.now + timedelta(minutes=2))
        self.assertEqual(self.rec.registration_last_edited_at, self.rec.registration_last_saved_at)
        self.assertEqual(self.rec.registration_last_edited_by, self.user)
        last = self.rec.registration_last_saved_at
        self.assertEqual(self.client.post(url, dict(self.profile(), mobile='bad')).status_code, 200)
        self.rec.refresh_from_db(); self.assertEqual(self.rec.registration_last_saved_at, last)

    def test_case_save_metadata_does_not_reset_first_completion_or_wait(self):
        self.rec.registration_completed_at = self.now
        self.rec.save(update_fields=['registration_completed_at'])
        url = reverse('customers:case_save')
        data = dict(reception=self.rec.pk, condition='cash', job='private', credit_rank='A1', quantity=1, visit_result='review')
        for minutes, quantity in [(1, 1), (2, 1), (3, 2)]:
            with patch('django.utils.timezone.now', return_value=self.now + timedelta(minutes=minutes)):
                self.assertEqual(self.client.post(url, dict(data, quantity=quantity)).status_code, 302)
            self.rec.refresh_from_db()
            self.assertEqual(self.rec.case_completed_at, self.now + timedelta(minutes=1))
            self.assertEqual(self.rec.case_wait_timing['seconds'], 60)
            if minutes < 3:
                self.assertIsNone(self.rec.case_last_edited_at)
        self.assertEqual(self.rec.case_last_edited_at, self.now + timedelta(minutes=3))
        page = self.client.get(reverse('customers:hub'), {'tab': 'case', 'r': self.rec.pk})
        for label in ['ثبت اولیه', 'آخرین ذخیره', 'آخرین ویرایش', 'مجموع انتظار']:
            self.assertContains(page, label)

    def candidate(self):
        self.person.is_interviewer = True; self.person.save(update_fields=['is_interviewer'])
        self.rec.person_type = 'interviewer'; self.rec.arrived_at = self.now - timedelta(minutes=10)
        self.rec.save(update_fields=['person_type', 'arrived_at'])
        ad = HiringAd.objects.create(platform='jobvision', number=1000, role_key='role:sales', role_title='فروش')
        application = HiringApplication.objects.create(reception=self.rec, job_ad=ad)
        return application, ad

    def test_hiring_timeline_contains_each_session_referrals_wait_and_outcome(self):
        app, ad = self.candidate()
        HiringReferral.objects.create(application=app, from_user=self.user, to_user=self.user, actor=self.user, note='ارجاع آزمایشی')
        session = InterviewSession.objects.create(application=app, round_number=1, kind='first', arrived_at=self.rec.arrived_at,
            started_at=self.now, ended_at=self.now + timedelta(minutes=5), waiting_seconds=600, interviewer=self.user,
            saved_at=self.now + timedelta(minutes=6), saved_by=self.user, result='repeat', next_interview_at=self.now + timedelta(days=1))
        app.latest_session = session; app.status = 'repeat'; app.save()
        page = self.client.get(reverse('customers:hub'), {'tab': 'hiring', 'r': self.rec.pk})
        for label in ['روند مراجعه استخدام', 'مجموع انتظار', 'آخرین ذخیره', 'آخرین ویرایش', 'ارجاع آزمایشی', 'مصاحبه بعد']:
            self.assertContains(page, label)
        self.assertContains(page, 'در سوابق ثبت نشده')
        journey = page.content.decode().split('روند مراجعه استخدام', 1)[1].split('</details>', 1)[0]
        self.assertNotIn('تحلیل مشتری', journey)

    def test_interview_edits_preserve_first_actor_and_distinguish_unchanged_save(self):
        app, ad = self.candidate()
        session = InterviewSession.objects.create(application=app, round_number=1, kind='first', interviewer=self.user, started_at=self.now)
        data = dict(job_ad=ad.pk, national_id='1234567891', behavior='friendly', fit='high', seriousness='high', questions='technical', grade='A', result='rejected', rejection_reason='skills')
        with patch('django.utils.timezone.now', return_value=self.now + timedelta(minutes=3)):
            self.assertEqual(self.client.post(reverse('customers:interview_save', args=[session.pk]), data).status_code, 302)
        session.refresh_from_db(); first = session.saved_at
        other = User.objects.create_superuser('journey_second_actor'); self.client.force_login(other)
        for minute, grade in [(4, 'A'), (5, 'B')]:
            with patch('django.utils.timezone.now', return_value=self.now + timedelta(minutes=minute)):
                self.assertEqual(self.client.post(reverse('customers:interview_edit', args=[session.pk]), dict(data, grade=grade)).status_code, 302)
            session.refresh_from_db(); self.assertEqual(session.saved_at, first); self.assertEqual(session.saved_by, self.user); self.assertEqual(session.first_saved_by, self.user)
            if minute == 4: self.assertIsNone(session.last_edited_at)
        self.assertEqual(session.last_edited_by, other)
        self.assertEqual(session.last_saved_at, self.now + timedelta(minutes=5))
        with patch('django.utils.timezone.now', return_value=self.now + timedelta(minutes=6)):
            changed_identity = dict(data, grade='B', national_id='0077611616')
            self.assertEqual(self.client.post(reverse('customers:interview_edit', args=[session.pk]), changed_identity).status_code, 302)
        session.refresh_from_db()
        self.assertEqual(session.last_edited_at, self.now + timedelta(minutes=6))

    def test_hiring_timeline_does_not_expose_details_without_hiring_permission_or_ownership(self):
        self.candidate()
        outsider = User.objects.create_user('journey_outsider')
        outsider.groups.add(Group.objects.get_or_create(name='کارشناس فروش')[0])
        request = RequestFactory().get('/'); request.user = outsider
        output = render_to_string('customers/_candidate_visit_details.html', {'request': request, 'rec': self.rec, 'user_permissions': {'customers.hiring'}})
        self.assertNotIn('روند مراجعه استخدام', output)
