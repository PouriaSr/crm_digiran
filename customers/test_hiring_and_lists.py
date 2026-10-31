"""Hiring branching, permissions, read-only records and server-side list search."""
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserPermissionOverride
from accounts.permissions import PERMISSIONS, get_user_permissions
from .models import Customer, CustomerCase, Reception


class HiringAndListsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('hiring_admin')
        cls.manager = cls.user('hiring_manager', 'مدیر فروش')
        cls.secretary = cls.user('hiring_secretary', 'منشی')
        cls.operator = cls.user('hiring_operator', 'اپراتور')
        cls.candidate = Customer.objects.create(name='متقاضی آزمایشی', mobile='09121234567',
                                               notes='شرح ثبت‌شده قبل از پذیرش', address='نشانی قبلی',
                                               email='candidate@example.com', assigned_to=cls.operator)
        cls.customer = Customer.objects.create(name='مشتری فروش', mobile='09120000000', assigned_to=cls.admin)

    @staticmethod
    def user(name, group):
        user = User.objects.create_user(name)
        user.groups.add(Group.objects.get_or_create(name=group)[0])
        return user

    def setUp(self):
        self.client.force_login(self.admin)
        self.hub = reverse('customers:hub')
        self.action = reverse('customers:reception_action')

    def arrival(self, person='interviewer'):
        return self.client.post(self.action, {'action': 'arrive', 'customer': self.candidate.pk, 'person_type': person})

    def grant(self, user, key, value=True):
        UserPermissionOverride.objects.update_or_create(user=user, permission_key=key, defaults={'granted': value})

    def test_hiring_has_same_default_roles_as_case_and_its_own_override(self):
        self.assertEqual(set(PERMISSIONS['customers.hiring']), set(PERMISSIONS['customers.case']))
        for user, expected in ((self.admin, True), (self.manager, True), (self.secretary, False), (self.operator, False)):
            self.client.force_login(user)
            response = self.client.get(self.hub, {'tab': 'hiring'})
            self.assertEqual(response.status_code, 200 if expected else 403)
        self.grant(self.operator, 'customers.case')
        self.assertNotIn('customers.hiring', get_user_permissions(self.operator))
        self.grant(self.operator, 'customers.hiring')
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(self.hub, {'tab': 'hiring'}).status_code, 200)
        self.grant(self.operator, 'customers.hiring', False)
        self.assertEqual(self.client.get(self.hub, {'tab': 'hiring'}).status_code, 403)

    def test_authorized_arrival_opens_hiring_and_preserves_existing_information(self):
        now = timezone.now()
        response = self.arrival()
        self.assertIn('tab=hiring', response['Location'])
        rec = Reception.objects.get(customer=self.candidate)
        self.assertGreaterEqual(rec.wait_started_at, now)
        page = self.client.get(response['Location'])
        self.assertContains(page, 'شرح ثبت‌شده قبل از پذیرش')
        self.assertContains(page, 'نشانی قبلی')
        self.assertContains(page, 'candidate@example.com')
        self.assertEqual(page.context['hiring_records'].paginator.count, 1)
        self.assertTrue(rec.is_waiting)
        self.assertFalse(CustomerCase.objects.exists())

    def test_secretary_can_register_interview_visitor_without_gaining_hiring_access(self):
        self.client.force_login(self.secretary)
        response = self.arrival()
        self.assertIn('tab=reception', response['Location'])
        self.assertNotIn('customers.hiring', get_user_permissions(self.secretary))
        self.assertEqual(self.client.get(self.hub, {'tab': 'hiring'}).status_code, 403)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(self.hub, {'tab': 'hiring'}).context['hiring_records'].paginator.count, 1)

    def test_interviewers_are_blocked_from_customer_workflow_even_with_old_completed_fields(self):
        self.arrival()
        rec = Reception.objects.get(customer=self.candidate)
        rec.referred_at = rec.case_completed_at = rec.registration_completed_at = timezone.now()
        rec.save()
        case = CustomerCase.objects.create(customer=self.candidate, condition='cash', job='private', credit_rank='A1')
        page = self.client.get(self.hub, {'tab': 'case', 'r': rec.pk})
        self.assertIsNone(page.context['case_record'])
        self.assertFalse(page.context['case_choices'].exists())
        self.assertFalse(self.client.get(self.hub, {'tab': 'registration'}).context['registration_unlocked'])
        post = self.client.post(reverse('customers:case_save'), {'reception': rec.pk, 'condition': 'credit'})
        self.assertEqual(post.status_code, 409)
        self.assertEqual(self.client.get(reverse('customers:registration_form', args=[rec.pk])).status_code, 409)
        self.assertEqual(self.client.post(reverse('customers:registration_form', args=[rec.pk]), {'name': 'تغییر'}).status_code, 409)
        case.refresh_from_db(); self.assertEqual(case.condition, 'cash')
        self.assertContains(self.client.get(self.hub, {'tab': 'hiring'}), 'A1')

    def test_hiring_list_contains_no_customers_and_no_duplicate_people(self):
        old = Reception.objects.create(customer=self.candidate, person_type='interviewer', workflow_version=1)
        self.arrival()
        Reception.objects.create(customer=self.customer, person_type='customer')
        page = self.client.get(self.hub, {'tab': 'hiring'})
        rows = list(page.context['hiring_records'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].customer_id, self.candidate.pk)
        self.assertNotEqual(rows[0].pk, old.pk)
        self.assertEqual(Reception.objects.count(), 3)

    def test_legacy_interviewers_are_visible_without_rewriting_old_records(self):
        old = Reception.objects.create(customer=self.candidate, person_type='interviewer', workflow_version=1,
                                       wait_minutes_total=45, is_waiting=False)
        page = self.client.get(self.hub, {'tab': 'hiring'})
        self.assertContains(page, 'سابقه قبلی')
        self.assertIn(old, page.context['hiring_records'])
        old.refresh_from_db(); self.assertIsNone(old.wait_started_at)
        self.assertIsNone(old.referred_at)
        self.assertEqual(old.wait_minutes_total, 45)

    def test_hiring_referral_uses_hiring_permission_and_stops_timer(self):
        self.grant(self.operator, 'customers.hiring')
        self.client.force_login(self.secretary); self.arrival()
        rec = Reception.objects.get(customer=self.candidate)
        response = self.client.post(self.action, {'action': 'refer', 'reception': rec.pk, 'user': self.operator.pk})
        self.assertEqual(response.status_code, 302)
        rec.refresh_from_db(); self.assertFalse(rec.is_waiting)
        self.assertIsNotNone(rec.referred_at)
        self.assertIsNone(rec.case_completed_at)
        self.assertNotIn('customers.case', get_user_permissions(self.operator))
        self.client.force_login(self.operator)
        self.assertIn(rec, self.client.get(self.hub, {'tab': 'hiring'}).context['hiring_records'])
        self.assertEqual(self.client.get(reverse('customers:hiring_clock')).json()['waiting'], [])
        self.assertEqual(self.client.get(reverse('customers:reception_clock')).status_code, 403)

    def test_explicit_hiring_denial_rejects_target_without_affecting_customer_referrals(self):
        self.grant(self.manager, 'customers.hiring', False)
        self.arrival(); rec = Reception.objects.get(customer=self.candidate)
        response = self.client.post(self.action, {'action': 'refer', 'reception': rec.pk, 'user': self.manager.pk})
        self.assertEqual(response.status_code, 400)
        rec.refresh_from_db(); self.assertTrue(rec.is_waiting)
        self.assertIsNone(rec.referred_at)

    def test_custom_hiring_user_sees_only_owned_candidates_and_no_extra_timing_ids(self):
        self.grant(self.operator, 'customers.hiring')
        self.arrival()
        another = Customer.objects.create(name='متقاضی دیگر', mobile='09129999999', assigned_to=self.manager)
        other_rec = Reception.objects.create(customer=another, person_type='interviewer', is_waiting=True,
                                             wait_started_at=timezone.now())
        self.client.force_login(self.operator)
        page = self.client.get(self.hub, {'tab': 'hiring'})
        self.assertEqual(page.context['hiring_records'].paginator.count, 1)
        self.assertNotContains(page, another.name)
        result = self.client.get(reverse('customers:hiring_clock')).json()
        self.assertNotIn(other_rec.pk, [x['pk'] for x in result['waiting']])
        self.assertNotIn(self.candidate.mobile, str(result))

    def test_read_only_hiring_view_does_not_change_data(self):
        self.arrival(); rec = Reception.objects.get(customer=self.candidate)
        original = (rec.updated_at, rec.wait_started_at, rec.referred_at, rec.case_completed_at)
        count = (Customer.objects.count(), Reception.objects.count(), CustomerCase.objects.count())
        for _ in range(2): self.client.get(self.hub, {'tab': 'hiring'})
        rec.refresh_from_db()
        self.assertEqual(original, (rec.updated_at, rec.wait_started_at, rec.referred_at, rec.case_completed_at))
        self.assertEqual(count, (Customer.objects.count(), Reception.objects.count(), CustomerCase.objects.count()))

    def test_name_phone_search_and_pagination_preserve_filter(self):
        self.arrival()
        self.assertEqual(self.client.get(self.hub, {'tab': 'hiring', 'workflow_q': 'متقاضی'}).context['hiring_records'].paginator.count, 1)
        self.assertEqual(self.client.get(self.hub, {'tab': 'hiring', 'workflow_q': '۰۹۱۲۱۲۳۴۵۶۷'}).context['hiring_records'].paginator.count, 1)
        self.assertEqual(self.client.get(self.hub, {'tab': 'hiring', 'workflow_q': 'ناموجود'}).context['hiring_records'].paginator.count, 0)
        for i in range(31):
            customer = Customer.objects.create(name=f'متقاضی شماره {i}', mobile=f'09130000{i:03d}', assigned_to=self.admin)
            Reception.objects.create(customer=customer, person_type='interviewer')
        page = self.client.get(self.hub, {'tab': 'hiring', 'workflow_q': 'متقاضی', 'hiring_page': '2'})
        self.assertEqual(page.context['hiring_records'].paginator.count, 32)
        self.assertEqual(len(page.context['hiring_records']), 2)
        self.assertContains(page, 'hiring_page=1&workflow_q=')
