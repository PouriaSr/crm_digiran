"""Integration coverage for the staged reception workflow and per-tab access."""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse, get_script_prefix, set_script_prefix
from django.utils import timezone

from accounts.models import UserPermissionOverride, UserRoleProfile
from accounts.permissions import get_user_permissions, get_user_role, get_user_role_display
from accounts.forms import UserEditForm
from .models import Customer, CustomerCase, Reception


class ReceptionWorkflowTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('flow_admin')
        cls.manager = cls.make_user('flow_manager', 'مدیر فروش')
        cls.secretary = cls.make_user('flow_secretary', 'منشی')
        cls.operator = cls.make_user('flow_operator', 'اپراتور')
        cls.peer = cls.make_user('flow_peer', 'مدیر فروش')
        cls.customer = Customer.objects.create(name='مراجعه آزمایشی', mobile='09121234567',
                                              stage='lead', source='direct', notes='یادداشت قبلی',
                                              assigned_to=cls.operator, created_by=cls.operator)

    @staticmethod
    def make_user(username, group):
        user = User.objects.create_user(username)
        user.groups.add(Group.objects.get_or_create(name=group)[0])
        return user

    def setUp(self):
        self.client.force_login(self.secretary)
        self.action = reverse('customers:reception_action')
        self.hub = reverse('customers:hub')

    def arrive(self, kind='customer'):
        response = self.client.post(self.action, {'action': 'arrive', 'customer': self.customer.pk, 'person_type': kind})
        self.assertEqual(response.status_code, 302)
        return Reception.objects.get(customer=self.customer, workflow_version=2, registration_completed_at=None)

    def refer(self, rec, target=None):
        return self.client.post(self.action, {'action': 'refer', 'reception': rec.pk, 'user': (target or self.manager).pk})

    def save_case(self, rec, **values):
        data = {'reception': rec.pk, 'condition': 'cash', 'job': 'private', 'credit_rank': 'A1',
                'quantity': '1', 'visit_result': 'review'}
        data.update(values)
        return self.client.post(reverse('customers:case_save'), data)

    def profile_data(self):
        return {'name': self.customer.name, 'mobile': self.customer.mobile, 'source': 'direct',
                'stage': 'lead', 'notes': 'یادداشت قبلی', 'address': 'آدرس کامل', 'email': 'test@example.com'}

    def test_default_tab_access_and_direct_urls(self):
        for user, tabs in [(self.secretary, {'info', 'reception'}), (self.operator, {'info'}),
                           (self.manager, {'info', 'reception', 'case', 'registration', 'hiring', 'invoice'})]:
            self.client.force_login(user)
            for tab in ('info', 'reception', 'case', 'registration', 'hiring', 'invoice'):
                response = self.client.get(self.hub, {'tab': tab})
                self.assertEqual(response.status_code, 200 if tab in tabs else 403, (user.username, tab))
                if response.status_code == 200:
                    self.assertEqual(set(response.context['allowed_hub_tabs']), tabs)
            response = self.client.get(self.hub)
            self.assertEqual(response.status_code, 200)

    def test_arrival_uses_server_time_and_one_question(self):
        now = datetime(2026, 10, 29, 10, 20, 30, tzinfo=dt_timezone.utc)
        with patch('customers.reception_workflow.timezone.now', return_value=now):
            rec = self.arrive()
        self.assertEqual(rec.wait_started_at, now)
        self.assertTrue(rec.is_waiting)
        self.assertIsNone(rec.referred_at)
        body = self.client.get(self.hub, {'tab': 'reception'}).content.decode()
        for old in ('name="has_visit"', 'name="wait_choice"', 'پایان انتظار'):
            self.assertNotIn(old, body)
        self.assertIn('data-wait-start=', body)
        self.assertIn('یادداشت قبلی', body)

    def test_duplicate_arrival_preserves_clock_and_type(self):
        rec = self.arrive()
        start = rec.wait_started_at
        self.client.post(self.action, {'action': 'answer', 'customer': self.customer.pk,
                                      'person_type': 'interviewer', 'wait_started_at': '2000-01-01'})
        rec.refresh_from_db()
        self.assertEqual(Reception.objects.count(), 1)
        self.assertEqual(rec.wait_started_at, start)
        self.assertEqual(rec.person_type, 'customer')

    def test_queue_preserves_and_displays_previous_call_information(self):
        from calls.models import Call
        Call.objects.create(customer=self.customer, call_number=self.customer.mobile,
                            caller_name=self.customer.name, contact_type='incoming',
                            purpose='support', status='answered', requested_condition='retired',
                            notes='جزئیات تماس قبلی')
        self.arrive()
        page = self.client.get(self.hub, {'tab': 'reception'})
        self.assertContains(page, 'آخرین تماس و شرایط درخواستی')
        self.assertContains(page, 'بازنشسته')
        self.assertContains(page, 'جزئیات تماس قبلی')

    def test_unknown_types_and_removed_actions_rejected_without_write(self):
        self.assertEqual(self.client.post(self.action, {'action': 'arrive', 'customer': self.customer.pk,
                                                       'person_type': 'unknown'}).status_code, 400)
        self.assertEqual(Reception.objects.count(), 0)
        for action in ('end_wait', 'submit_info'):
            self.assertEqual(self.client.post(self.action, {'action': action, 'customer': self.customer.pk}).status_code, 400)

    def test_referral_stops_clock_once_and_transfers_responsibility(self):
        rec = self.arrive()
        start = timezone.now() - timedelta(minutes=12, seconds=23)
        Reception.objects.filter(pk=rec.pk).update(wait_started_at=start)
        now = timezone.now()
        with patch('customers.reception_workflow.timezone.now', return_value=now):
            self.assertEqual(self.refer(rec).status_code, 302)
        rec.refresh_from_db(); self.customer.refresh_from_db()
        self.assertEqual(rec.wait_ended_at, now)
        self.assertEqual(rec.referred_at, now)
        self.assertEqual(rec.referred_by, self.secretary)
        self.assertEqual(rec.referred_to, self.manager)
        self.assertEqual(self.customer.assigned_to, self.manager)
        self.assertEqual(rec.wait_seconds, int((now - start).total_seconds()))
        self.assertFalse(rec.is_waiting)
        self.refer(rec, self.peer)
        rec.refresh_from_db()
        self.assertEqual(rec.referred_to, self.manager)
        self.assertEqual(rec.wait_ended_at, now)

    def test_invalid_referral_keeps_waiting(self):
        rec = self.arrive()
        self.assertEqual(self.refer(rec, self.operator).status_code, 400)
        self.operator.is_active = False; self.operator.save()
        self.assertEqual(self.refer(rec, self.operator).status_code, 404)
        rec.refresh_from_db()
        self.assertTrue(rec.is_waiting)
        self.assertIsNone(rec.wait_ended_at)

    def test_explicit_case_denial_excludes_referral_target(self):
        UserPermissionOverride.objects.create(user=self.manager, permission_key='customers.case', granted=False)
        rec = self.arrive()
        self.assertEqual(self.refer(rec).status_code, 400)
        page = self.client.get(self.hub, {'tab': 'reception'})
        self.assertNotIn(self.manager, page.context['referral_users'])

    def test_customer_completes_stages_without_potential_requirement(self):
        rec = self.arrive('customer')
        self.assertEqual(self.refer(rec).status_code, 302)
        self.client.force_login(self.manager)
        self.assertFalse(self.client.get(self.hub, {'tab': 'registration'}).context['registration_unlocked'])
        self.assertEqual(self.save_case(rec).status_code, 302)
        page = self.client.get(self.hub, {'tab': 'registration'})
        self.assertTrue(page.context['registration_unlocked'])
        self.assertIn(rec.pk, [x.pk for x in page.context['registration_choices']])
        popup = reverse('customers:registration_form', args=[rec.pk])
        self.assertContains(self.client.get(popup), f'value="{self.customer.mobile}"')
        response = self.client.post(popup, self.profile_data(), HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 204)
        self.assertIn('tab=registration', response['HX-Redirect'])
        rec.refresh_from_db(); self.customer.refresh_from_db()
        self.assertIsNotNone(rec.registration_completed_at)
        self.assertEqual(self.customer.address, 'آدرس کامل')

    def test_case_and_registration_direct_post_cannot_skip_stages(self):
        rec = self.arrive()
        self.client.force_login(self.admin)
        self.assertEqual(self.save_case(rec).status_code, 409)
        popup = reverse('customers:registration_form', args=[rec.pk])
        self.assertEqual(self.client.get(popup).status_code, 409)
        self.assertEqual(self.client.post(popup, self.profile_data()).status_code, 409)
        self.assertFalse(CustomerCase.objects.exists())
        rec.refresh_from_db(); self.assertIsNone(rec.case_completed_at)

    def test_invalid_case_preserves_values_and_does_not_unlock(self):
        rec = self.arrive(); self.refer(rec)
        self.client.force_login(self.manager)
        response = self.save_case(rec, job='', cheque_other_name='نام باقی بماند')
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'نام باقی بماند', status_code=400)
        self.assertFalse(CustomerCase.objects.exists())
        rec.refresh_from_db(); self.assertIsNone(rec.case_completed_at)

    def test_registration_validation_and_repeat_submit_preserve_times(self):
        rec = self.arrive(); self.refer(rec)
        self.client.force_login(self.manager); self.save_case(rec)
        popup = reverse('customers:registration_form', args=[rec.pk])
        self.client.post(popup, dict(self.profile_data(), mobile='123'))
        rec.refresh_from_db(); self.assertIsNone(rec.registration_completed_at)
        self.client.post(popup, self.profile_data())
        rec.refresh_from_db(); stamp = rec.registration_completed_at
        self.client.post(popup, dict(self.profile_data(), assigned_to=self.operator.pk))
        rec.refresh_from_db(); self.customer.refresh_from_db()
        self.assertEqual(rec.registration_completed_at, stamp)
        self.assertEqual(self.customer.assigned_to, self.manager)

    def test_custom_permissions_work_independently_and_ownership_is_enforced(self):
        UserPermissionOverride.objects.create(user=self.operator, permission_key='customers.case', granted=True)
        UserPermissionOverride.objects.create(user=self.operator, permission_key='customers.registration', granted=True)
        UserPermissionOverride.objects.create(user=self.operator, permission_key='customers.info', granted=False)
        rec = self.arrive(); self.refer(rec, self.operator)
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(self.hub, {'tab': 'info'}).status_code, 403)
        self.assertEqual(self.save_case(rec).status_code, 302)
        popup = reverse('customers:registration_form', args=[rec.pk])
        self.assertEqual(self.client.get(popup).status_code, 200)
        self.customer.assigned_to = self.manager; self.customer.save()
        self.assertEqual(self.save_case(rec).status_code, 403)
        self.assertEqual(self.client.get(popup).status_code, 403)
        self.assertEqual(self.client.post(popup, self.profile_data()).status_code, 403)

    def test_secretary_cannot_open_profile_or_case_even_by_direct_post(self):
        rec = self.arrive(); self.refer(rec)
        self.assertEqual(self.save_case(rec).status_code, 403)
        self.assertEqual(self.client.get(reverse('customers:registration_form', args=[rec.pk])).status_code, 403)
        self.assertNotIn('id_national_id', self.client.get(self.hub, {'tab': 'reception'}).content.decode())

    def test_unique_open_visit_database_constraint_and_legacy_archive(self):
        legacy = Reception.objects.create(customer=self.customer, person_type='customer', workflow_version=1)
        rec = self.arrive()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Reception.objects.create(customer=self.customer, person_type='customer')
        page = self.client.get(self.hub, {'tab': 'reception'})
        self.assertIn(legacy, page.context['legacy_receptions'])
        self.assertNotIn(legacy.pk, [x.pk for x in page.context['reception_records']])
        self.assertIn(rec.pk, [x.pk for x in page.context['reception_records']])

    @override_settings(FORCE_SCRIPT_NAME='/test')
    def test_workflow_urls_keep_cpanel_prefix(self):
        prefix = get_script_prefix()
        set_script_prefix('/test/')
        try:
            rec = self.arrive()
            self.assertEqual(self.refer(rec)['Location'], f'/test/customers/hub/?tab=reception&r={rec.pk}')
            self.client.force_login(self.manager)
            self.client.post('/customers/hub/case/save/', {'reception': rec.pk, 'condition': 'cash', 'job': 'private', 'credit_rank': 'A1', 'visit_result': 'review', 'quantity': 1})
            popup = self.client.get(f'/customers/hub/registration/{rec.pk}/')
            self.assertContains(popup, f'/test/customers/hub/registration/{rec.pk}/?is_modal=1')
        finally:
            set_script_prefix(prefix)

    def test_clock_reports_only_server_time_and_timing_ids(self):
        rec = self.arrive()
        result = self.client.get(reverse('customers:reception_clock')).json()
        self.assertEqual(set(result), {'server_now', 'waiting'})
        self.assertEqual(result['waiting'][0]['pk'], rec.pk)
        self.assertNotIn(self.customer.name, str(result))
        self.refer(rec)
        self.assertEqual(self.client.get(reverse('customers:reception_clock')).json()['waiting'], [])

    def test_custom_role_title_is_separate_from_role_and_permissions(self):
        self.assertTrue(UserEditForm(instance=self.operator)['is_active'].value())
        data = {'username': self.operator.username, 'first_name': 'کاربر', 'last_name': '', 'email': '',
                'role': 'operator', 'role_title': 'مدیر نمایشی', 'is_active': 'on',
                'perm__customers_reception': 'allow', 'perm__customers_info': 'deny'}
        form = UserEditForm(data, instance=self.operator)
        self.assertTrue(form.is_valid(), form.errors)
        form.save(); self.operator.refresh_from_db()
        self.assertEqual(get_user_role(self.operator), 'operator')
        self.assertEqual(get_user_role_display(self.operator), 'مدیر نمایشی')
        perms = get_user_permissions(self.operator)
        self.assertIn('customers.reception', perms)
        self.assertNotIn('customers.info', perms)
        self.assertNotIn('customers.case', perms)
        self.client.force_login(self.operator)
        page = self.client.get(self.hub)
        self.assertEqual(page.context['active_tab'], 'reception')
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('accounts:user_list')), 'مدیر نمایشی')
