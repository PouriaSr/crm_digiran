"""CRM lead/potential tags no longer gate the admission workflow."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from customers.models import Customer, CustomerCase, Reception


class StageConsistencyTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('cons_admin')
        cls.pot = Customer.objects.create(name='بالقوه', mobile='09121280001', stage='potential', assigned_to=cls.user)
        cls.lead = Customer.objects.create(name='سرنخ', mobile='09121280002', stage='lead', assigned_to=cls.user)

    def setUp(self):
        self.client.force_login(self.user)
        self.hub = reverse('customers:hub')

    def referred(self, customer):
        self.client.post(reverse('customers:reception_action'), {'customer': customer.pk, 'action': 'arrive', 'person_type': 'customer'})
        rec = Reception.objects.get(customer=customer)
        self.client.post(reverse('customers:reception_action'), {'reception': rec.pk, 'action': 'refer', 'user': self.user.pk})
        return rec

    def save_case(self, rec):
        return self.client.post(reverse('customers:case_save'), {'reception': rec.pk, 'condition': 'cash', 'job': 'private', 'credit_rank': 'B1', 'visit_result': 'bought', 'quantity': 1})

    def test_kpi_counts_stage_leads(self):
        self.assertEqual(self.client.get(self.hub).context['stats']['total_leads'], 1)

    def test_case_available_for_referred_lead(self):
        rec = self.referred(self.lead)
        self.assertEqual(self.client.get(self.hub, {'tab': 'case', 'r': rec.pk}).context['case_record'], rec)

    def test_case_available_for_referred_potential(self):
        rec = self.referred(self.pot)
        self.assertEqual(self.client.get(self.hub, {'tab': 'case', 'r': rec.pk}).context['case_record'], rec)

    def test_server_allows_case_save_for_referred_lead(self):
        self.assertEqual(self.save_case(self.referred(self.lead)).status_code, 302)
        self.assertTrue(CustomerCase.objects.filter(customer=self.lead).exists())

    def test_server_allows_case_save_for_referred_potential(self):
        self.assertEqual(self.save_case(self.referred(self.pot)).status_code, 302)
        self.assertTrue(CustomerCase.objects.filter(customer=self.pot).exists())

    def test_info_submitted_flag_does_not_bypass_referral(self):
        rec = Reception.objects.create(customer=self.lead, person_type='customer', info_submitted=True)
        self.assertEqual(self.save_case(rec).status_code, 409)
        self.assertFalse(CustomerCase.objects.exists())
