"""تست ماندگار: هم‌خوانی stage در آمار، قفل پرونده و محافظت سرور."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer, CustomerCase, Reception


class StageConsistencyTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('cons_admin', password='t123456')
        cls.pot = Customer.objects.create(name='بالقوه', mobile='09121280001',
                                          stage='potential', needs_followup=True,
                                          assigned_to=cls.user, created_by=cls.user)
        cls.lead = Customer.objects.create(name='سرنخ', mobile='09121280002',
                                           stage='lead', assigned_to=cls.user,
                                           created_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)
        self.hub = reverse('customers:hub')

    def _complete_reception(self, customer):
        self.client.post(reverse('customers:reception_action'),
                         {'customer': customer.pk, 'action': 'answer',
                          'person_type': 'customer', 'has_visit': 'yes',
                          'wait_choice': '30'})
        self.client.post(reverse('customers:reception_action'),
                         {'customer': customer.pk, 'action': 'end_wait'})
        Reception.objects.filter(customer=customer).update(info_submitted=True)

    def test_kpi_counts_stage_leads(self):
        body = self.client.get(f'{self.hub}?tab=info').content.decode('utf-8')
        # فقط یک سرنخ (مشتری دوم) داریم
        self.assertIn('سرنخ‌ها</div>', body)
        self.assertRegex(body, r'سرنخ‌ها</div>\s*<div[^>]*>\s*۱\s*</div>')

    def test_case_locked_for_lead_even_after_reception(self):
        self._complete_reception(self.lead)
        body = self.client.get(f'{self.hub}?tab=case&c={self.lead.pk}').content.decode('utf-8')
        self.assertIn('caseUnlocked: false', body)

    def test_case_open_for_potential(self):
        self._complete_reception(self.pot)
        body = self.client.get(f'{self.hub}?tab=case&c={self.pot.pk}').content.decode('utf-8')
        self.assertIn('caseUnlocked: true', body)

    def test_server_blocks_case_save_for_lead(self):
        self._complete_reception(self.lead)
        self.client.post(reverse('customers:case_save'), {
            'customer': self.lead.pk, 'condition': 'cash', 'job': 'private',
            'credit_rank': 'B1', 'visit_result': 'bought', 'quantity': 1,
        })
        self.assertFalse(CustomerCase.objects.filter(customer=self.lead).exists())

    def test_server_allows_case_save_for_potential(self):
        self._complete_reception(self.pot)
        self.client.post(reverse('customers:case_save'), {
            'customer': self.pot.pk, 'condition': 'cash', 'job': 'private',
            'credit_rank': 'B1', 'visit_result': 'bought', 'quantity': 1,
        })
        self.assertTrue(CustomerCase.objects.filter(customer=self.pot).exists())

    def test_reception_case_button_only_for_potential(self):
        self._complete_reception(self.pot)
        self._complete_reception(self.lead)
        pot_body = self.client.get(f'{self.hub}?tab=reception&c={self.pot.pk}').content.decode('utf-8')
        lead_body = self.client.get(f'{self.hub}?tab=reception&c={self.lead.pk}').content.decode('utf-8')
        self.assertRegex(pot_body, r'<a[^>]*>\s*پرونده مشتری\s*</a>')
        self.assertNotRegex(lead_body, r'<a[^>]*>\s*پرونده مشتری\s*</a>')
