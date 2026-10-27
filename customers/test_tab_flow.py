"""تست ماندگار: ترتیب تب‌ها و قفل تب پرونده تا تکمیل پذیرش."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer, Reception


class TabOrderAndCaseLockTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('tab_admin', password='t123456')
        cls.customer = Customer.objects.create(name='مشتری تب', mobile='09121241001',
                                               stage='potential', assigned_to=cls.user,
                                               created_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)
        self.hub = reverse('customers:hub')

    def _body(self, url=None):
        return self.client.get(url or f'{self.hub}?tab=info').content.decode('utf-8')

    def test_tab_order_reception_before_case(self):
        body = self._body()
        i_rec = body.find("tab = 'reception';")
        i_case = body.find("tab = 'case'")
        i_inv = body.find("tab = 'invoice';")
        self.assertTrue(0 < i_rec < i_case < i_inv,
                        'ترتیب باید پذیرش → پرونده → فاکتورها باشد')

    def test_case_locked_before_reception(self):
        body = self._body()
        self.assertIn('caseUnlocked: false', body)
        self.assertIn('🔒', body)

    def test_direct_case_url_redirects_to_reception(self):
        body = self._body(f'{self.hub}?tab=case&c={self.customer.pk}')
        self.assertIn("if (t === 'case' && !false) return 'reception';", body)
        self.assertIn('تب پرونده هنوز فعال نیست', body)

    def test_case_unlocked_after_reception_completed(self):
        c = self.customer
        self.client.post(reverse('customers:reception_action'),
                         {'customer': c.pk, 'action': 'answer', 'person_type': 'customer',
                          'has_visit': 'yes', 'wait_choice': '30'})
        self.client.post(reverse('customers:reception_action'),
                         {'customer': c.pk, 'action': 'end_wait'})
        self.client.post(reverse('customers:reception_action'),
                         {'customer': c.pk, 'action': 'submit_info'})

        body = self._body(f'{self.hub}?tab=case&c={c.pk}')
        self.assertIn('caseUnlocked: true', body)
        self.assertIn('📁', body)
        self.assertNotIn('تب پرونده هنوز فعال نیست', body)
        self.assertIn('شرایط', body)

    def test_unlock_requires_info_submitted_not_just_answers(self):
        c = self.customer
        Reception.objects.create(customer=c, person_type='customer',
                                 has_visit='yes', wait_choice='30',
                                 is_waiting=False, info_submitted=False)
        body = self._body(f'{self.hub}?tab=case&c={c.pk}')
        self.assertIn('caseUnlocked: false', body)
