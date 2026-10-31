"""Interview visitors are routed to hiring while retaining their admission records."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from customers.models import Customer, Reception


class InterviewerFlowTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('int_admin')
        cls.cand = Customer.objects.create(name='کاندید تست', mobile='09121290001', assigned_to=cls.user)
        cls.other = Customer.objects.create(name='مشتری نمونه', mobile='09121290002', assigned_to=cls.user)

    def setUp(self):
        self.client.force_login(self.user)
        self.hub = reverse('customers:hub')
        self.action = reverse('customers:reception_action')

    def arrive(self):
        self.client.post(self.action, {'customer': self.cand.pk, 'action': 'arrive', 'person_type': 'interviewer'})
        return Reception.objects.get(customer=self.cand)

    def test_flag_set_for_interviewer(self):
        self.arrive(); self.cand.refresh_from_db()
        self.assertTrue(self.cand.is_interviewer)

    def test_interviewers_remain_in_shared_information_list(self):
        self.arrive()
        ids = [row.pk for row in self.client.get(self.hub).context['customers']]
        self.assertIn(self.cand.pk, ids); self.assertIn(self.other.pk, ids)

    def test_interviewers_do_not_enter_customer_case_selector(self):
        rec = self.arrive()
        response = self.client.get(self.hub, {'tab': 'case'})
        self.assertFalse(response.context['case_choices'].exists())
        self.client.post(self.action, {'action': 'refer', 'reception': rec.pk, 'user': self.user.pk})
        self.assertNotIn(rec, self.client.get(self.hub, {'tab': 'case'}).context['case_choices'])
        self.assertIn(rec, self.client.get(self.hub, {'tab': 'hiring'}).context['hiring_records'])

    def test_reception_has_same_question_and_clock_for_both_types(self):
        self.arrive()
        response = self.client.get(self.hub, {'tab': 'reception'})
        self.assertContains(response, 'مراجعه‌کننده، مشتری است یا مصاحبه‌کننده؟')
        self.assertContains(response, 'data-wait-start=')
        self.assertNotContains(response, 'name="has_visit"')

    def test_old_recruitment_url_opens_hiring(self):
        self.arrive()
        response = self.client.get(self.hub, {'tab': 'recruitment'})
        self.assertEqual(response.context['active_tab'], 'hiring')
        self.assertContains(response, self.cand.name)

    def test_interviewers_are_not_ready_for_registration_just_on_arrival(self):
        self.arrive()
        response = self.client.get(self.hub, {'tab': 'registration'})
        self.assertFalse(response.context['registration_unlocked'])

    def test_repeated_arrival_cannot_change_active_visit_type(self):
        rec = self.arrive()
        self.client.post(self.action, {'customer': self.cand.pk, 'action': 'arrive', 'person_type': 'customer'})
        self.cand.refresh_from_db(); rec.refresh_from_db()
        self.assertTrue(self.cand.is_interviewer)
        self.assertEqual(rec.person_type, 'interviewer')

    def test_data_not_deleted(self):
        self.arrive()
        self.assertTrue(Customer.objects.filter(pk=self.cand.pk).exists())
        self.assertEqual(Reception.objects.filter(customer=self.cand).count(), 1)
