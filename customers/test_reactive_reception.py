"""Live waiting clocks now use server timestamps and explicit referrals."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from customers.models import Customer, Reception


class ReactiveReceptionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('react_admin')
        cls.c1 = Customer.objects.create(name='اولی', mobile='09121310001', assigned_to=cls.user)
        cls.c2 = Customer.objects.create(name='دومی', mobile='09121310002', assigned_to=cls.user)

    def setUp(self):
        self.client.force_login(self.user)
        self.hub = reverse('customers:hub')

    def arrive(self, customer):
        self.client.post(reverse('customers:reception_action'), {'customer': customer.pk, 'action': 'arrive', 'person_type': 'interviewer'})
        return Reception.objects.get(customer=customer)

    def test_clock_uses_server_baseline_and_monotonic_elapsed_time(self):
        self.arrive(self.c1)
        body = self.client.get(self.hub, {'tab': 'reception'}).content.decode()
        self.assertIn('data-server-now=', body)
        self.assertIn('performance.now()', body)

    def test_no_independent_end_wait_button(self):
        self.assertNotContains(self.client.get(self.hub, {'tab': 'reception'}), 'name="action" value="end_wait"')

    def test_no_browser_autofill(self):
        self.assertContains(self.client.get(self.hub, {'tab': 'reception'}), 'autocomplete="off"')

    def test_each_visitor_has_an_independent_clock(self):
        first = self.arrive(self.c1); second = self.arrive(self.c2)
        body = self.client.get(self.hub, {'tab': 'reception'}).content.decode()
        self.assertIn(f'data-reception-id="{first.pk}"', body)
        self.assertIn(f'data-reception-id="{second.pk}"', body)
        self.assertEqual(body.count('data-wait-start='), 2)

    def test_waiting_visit_is_absent_from_case_selector(self):
        self.arrive(self.c1)
        self.assertFalse(self.client.get(self.hub, {'tab': 'case'}).context['case_choices'].exists())

    def test_referral_enables_case_selector_without_info_submitted(self):
        rec = self.arrive(self.c1)
        rec.person_type='customer'; rec.save(update_fields=['person_type'])
        self.client.post(reverse('customers:reception_action'), {'reception': rec.pk, 'action': 'refer', 'user': self.user.pk})
        response = self.client.get(self.hub, {'tab': 'case', 'r': rec.pk})
        self.assertEqual(response.context['case_record'], rec)
        self.assertIsNotNone(response.context['case_form'])

    def test_hub_sends_no_cache_headers(self):
        self.assertIn('no-cache', self.client.get(self.hub)['Cache-Control'])
