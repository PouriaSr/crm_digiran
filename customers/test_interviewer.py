"""تست ماندگار: جریان مصاحبه‌کننده (واحد استخدام)."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer, Reception


class InterviewerFlowTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('int_admin', password='t123456')
        cls.cand = Customer.objects.create(name='کاندید تست', mobile='09121290001',
                                           stage='potential', needs_followup=True,
                                           assigned_to=cls.user, created_by=cls.user)
        cls.other = Customer.objects.create(name='مشتری نمونه', mobile='09121290002',
                                            stage='lead', assigned_to=cls.user,
                                            created_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)
        self.hub = reverse('customers:hub')

    def _answer(self, person, wait='45'):
        data = {'customer': self.cand.pk, 'action': 'answer',
                'person_type': person, 'wait_choice': wait}
        if person == 'customer':
            data['has_visit'] = 'yes'
        return self.client.post(reverse('customers:reception_action'), data)

    # ── ثبت به‌عنوان مصاحبه‌کننده ──
    def test_flag_set_for_interviewer(self):
        self._answer('interviewer')
        self.cand.refresh_from_db()
        self.assertTrue(self.cand.is_interviewer)

    def test_hidden_from_info_list(self):
        self._answer('interviewer')
        r = self.client.get(f'{self.hub}?tab=info')
        ids = [c.pk for c in r.context['customers']]
        self.assertNotIn(self.cand.pk, ids)
        self.assertIn(self.other.pk, ids)

    def test_hidden_from_case_selector(self):
        self._answer('interviewer')
        r = self.client.get(f'{self.hub}?tab=case&c={self.other.pk}')
        self.assertNotIn(self.cand.pk, [c.pk for c in r.context['case_customers']])

    # ── تب پذیرش شرطی ──
    def test_reception_shows_interviewer_question(self):
        self._answer('interviewer')
        body = self.client.get(f'{self.hub}?tab=reception&c={self.cand.pk}').content.decode('utf-8')
        self.assertIn('مصاحبه‌کننده چند دقیقه در سالن منتظر است؟', body)
        self.assertIn("x-show=\"person !== 'interviewer'\"", body)
        self.assertIn('پرونده مصاحبه‌کننده', body)

    # ── تب واحد استخدام ──
    def test_recruitment_tab_lists_interviewers(self):
        self._answer('interviewer')
        r = self.client.get(f'{self.hub}?tab=recruitment')
        self.assertIn('واحد استخدام', r.content.decode('utf-8'))
        self.assertIn(self.cand.pk, [x.customer_id for x in r.context['recruiter_rows']])

    def test_recruitment_tab_excludes_customers(self):
        r = self.client.get(f'{self.hub}?tab=recruitment')
        self.assertNotIn(self.other.pk, [x.customer_id for x in r.context['recruiter_rows']])

    # ── بازگشت به مشتری ──
    def test_switch_back_restores_visibility(self):
        self._answer('interviewer')
        self._answer('customer', '30')
        self.cand.refresh_from_db()
        self.assertFalse(self.cand.is_interviewer)

        r = self.client.get(f'{self.hub}?tab=info')
        self.assertIn(self.cand.pk, [c.pk for c in r.context['customers']])

        r2 = self.client.get(f'{self.hub}?tab=recruitment')
        self.assertNotIn(self.cand.pk, [x.customer_id for x in r2.context['recruiter_rows']])

    def test_data_not_deleted(self):
        self._answer('interviewer')
        self._answer('customer', '30')
        self.assertTrue(Reception.objects.filter(customer=self.cand).exists())
