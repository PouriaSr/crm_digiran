"""Ordered workflow tabs and registration gate are enforced on the server."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from customers.models import Customer, Reception


class TabOrderAndCaseLockTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('tab_admin')
        cls.customer = Customer.objects.create(name='مشتری تب', mobile='09121241001', assigned_to=cls.user)

    def setUp(self):
        self.client.force_login(self.user)
        self.hub = reverse('customers:hub')

    def test_tab_order(self):
        items = self.client.get(self.hub).context['hub_tab_items']
        self.assertEqual([item['key'] for item in items], ['info', 'reception', 'case', 'registration', 'invoice'])

    def test_registration_locked_before_case(self):
        response = self.client.get(self.hub)
        self.assertFalse(response.context['registration_unlocked'])
        self.assertContains(response, '🔒 ثبت اطلاعات')

    def test_direct_empty_case_url_does_not_open_a_form(self):
        response = self.client.get(self.hub, {'tab': 'case', 'c': self.customer.pk})
        self.assertIsNone(response.context['case_form'])
        self.assertEqual(response.context['active_tab'], 'case')

    def test_case_form_after_referral(self):
        self.client.post(reverse('customers:reception_action'), {'action': 'arrive', 'customer': self.customer.pk, 'person_type': 'customer'})
        rec = Reception.objects.get(customer=self.customer)
        self.client.post(reverse('customers:reception_action'), {'action': 'refer', 'reception': rec.pk, 'user': self.user.pk})
        response = self.client.get(self.hub, {'tab': 'case', 'r': rec.pk})
        self.assertIsNotNone(response.context['case_form'])
        self.assertFalse(response.context['registration_unlocked'])

    def test_old_info_submitted_flag_does_not_unlock_registration(self):
        Reception.objects.create(customer=self.customer, person_type='customer', has_visit='yes', wait_choice='30', info_submitted=True)
        self.assertFalse(self.client.get(self.hub, {'tab': 'registration'}).context['registration_unlocked'])
