"""تست ماندگار: واکنش لحظه‌ای تب پذیرش + قفل پرونده برای مصاحبه‌کننده."""
import re

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer, Reception


class ReactiveReceptionTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('react_admin', password='t123456')
        cls.c1 = Customer.objects.create(name='اولی', mobile='09121310001',
                                         stage='potential', assigned_to=cls.user,
                                         created_by=cls.user)
        cls.c2 = Customer.objects.create(name='دومی', mobile='09121310002',
                                         stage='lead', assigned_to=cls.user,
                                         created_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)
        self.hub = reverse('customers:hub')

    # ── ساختار واکنشی ──
    def test_panel_uses_shared_alpine_scope(self):
        body = self.client.get(f'{self.hub}?tab=reception&c={self.c1.pk}').content.decode('utf-8')
        self.assertIn('x-data="{ person:', body)

    def test_interviewer_case_button_always_rendered_toggleable(self):
        body = self.client.get(f'{self.hub}?tab=reception&c={self.c1.pk}').content.decode('utf-8')
        self.assertIn("x-show=\"person === 'interviewer'\"", body)

    def test_no_browser_autofill(self):
        body = self.client.get(f'{self.hub}?tab=reception&c={self.c1.pk}').content.decode('utf-8')
        self.assertIn('autocomplete="off"', body)

    # ── نفر قبلی ──
    def test_switching_customer_shows_fresh_state(self):
        body = self.client.get(f'{self.hub}?tab=reception&c={self.c2.pk}').content.decode('utf-8')
        self.assertIn('هنوز انتظاری شروع نشده', body)

    # ── قفل پرونده ──
    def _make_interviewer(self, customer):
        self.client.post(reverse('customers:reception_action'),
                         {'customer': customer.pk, 'action': 'answer',
                          'person_type': 'interviewer', 'wait_choice': '30'})
        self.client.post(reverse('customers:reception_action'),
                         {'customer': customer.pk, 'action': 'end_wait'})
        Reception.objects.filter(customer=customer).update(info_submitted=True)

    def test_case_locked_for_interviewer_even_with_info_submitted(self):
        self._make_interviewer(self.c1)
        body = self.client.get(f'{self.hub}?tab=case&c={self.c1.pk}').content.decode('utf-8')
        self.assertIn('caseUnlocked: false', body)
        self.assertIn('تب پرونده هنوز فعال نیست', body)

    def test_case_reopens_when_back_to_customer(self):
        self._make_interviewer(self.c1)
        self.client.post(reverse('customers:reception_action'),
                         {'customer': self.c1.pk, 'action': 'answer',
                          'person_type': 'customer', 'has_visit': 'yes',
                          'wait_choice': '30'})
        body = self.client.get(f'{self.hub}?tab=case&c={self.c1.pk}').content.decode('utf-8')
        self.assertIn('caseUnlocked: true', body)

    def test_hub_sends_no_cache_headers(self):
        r = self.client.get(f'{self.hub}?tab=reception&c={self.c1.pk}')
        cc = r.headers.get('Cache-Control', '')
        self.assertTrue('no-store' in cc or 'no-cache' in cc, f'Cache-Control={cc}')
