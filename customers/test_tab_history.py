"""تست ماندگار: تاریخچه تب پذیرش/پرونده + ثبت به‌روزرسانی."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer, CustomerCase, RecordUpdate, Reception


class TabHistoryTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('hist2_admin', password='t123456')
        cls.customer = Customer.objects.create(
            name='مشتری تاریخچه', mobile='09121360001', stage='potential',
            needs_followup=True, assigned_to=cls.user, created_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)
        self.hub = reverse('customers:hub')

    def _reception(self, person='customer', wait='30'):
        data = {'customer': self.customer.pk, 'action': 'answer',
                'person_type': person, 'wait_choice': wait}
        if person == 'customer':
            data['has_visit'] = 'yes'
        return self.client.post(reverse('customers:reception_action'), data)

    def _complete_reception(self):
        self._reception()
        rec = Reception.objects.get(customer=self.customer)
        self.client.post(reverse('customers:reception_action'),
                         {'reception': rec.pk, 'action': 'refer', 'user': self.user.pk})
        return rec

    # ── پذیرش ──
    def test_reception_history_section_rendered(self):
        self._reception()
        body = self.client.get(f'{self.hub}?tab=reception&c={self.customer.pk}').content.decode('utf-8')
        self.assertIn('مراجعه‌کنندگان و وضعیت انتظار', body)
        self.assertIn('مشتری تاریخچه', body)
        self.assertIn('data-reception-id=', body)

    def test_reception_history_in_context(self):
        self._reception()
        r = self.client.get(f'{self.hub}?tab=reception&c={self.customer.pk}')
        self.assertIn(self.customer.pk, [x.customer_id for x in r.context['reception_records']])

    def test_referral_logs_update(self):
        self._complete_reception()
        upd = RecordUpdate.objects.filter(customer=self.customer, scope='reception').latest('pk')
        self.assertEqual(upd.changes[0]['label'], 'ارجاع پذیرش')
        self.assertEqual(upd.changes[0]['new'], self.user.username)

    # ── پرونده ──
    def test_case_history_section_rendered(self):
        rec = self._complete_reception()
        self.client.post(reverse('customers:case_save'), {
            'reception': rec.pk, 'condition': 'cash', 'job': 'private',
            'credit_rank': 'A1', 'visit_result': 'bought', 'quantity': 1,
        })
        body = self.client.get(f'{self.hub}?tab=case&c={self.customer.pk}').content.decode('utf-8')
        self.assertIn('فهرست پرونده‌ها و اطلاعات این مرحله', body)

    def test_case_edit_logs_before_after(self):
        rec = self._complete_reception()
        self.client.post(reverse('customers:case_save'), {
            'reception': rec.pk, 'condition': 'cash', 'job': 'private',
            'credit_rank': 'A1', 'visit_result': 'bought', 'quantity': 1,
        })
        self.client.post(reverse('customers:case_save'), {
            'reception': rec.pk, 'condition': 'credit', 'job': 'freelance',
            'credit_rank': 'B2', 'visit_result': 'review', 'quantity': 2,
        })
        upd = RecordUpdate.objects.filter(customer=self.customer, scope='case').order_by('-id').first()
        self.assertTrue(any(ch['label'] == 'شرایط' and ch['old'] == 'نقد'
                            and ch['new'] == 'دارای اعتبار' for ch in upd.changes))
        self.assertTrue(any(ch['label'] == 'رتبه اعتباری' and ch['old'] == 'A1'
                            and ch['new'] == 'B2' for ch in upd.changes))

    def test_no_change_no_log(self):
        rec = self._complete_reception()
        self.client.post(reverse('customers:case_save'), {
            'reception': rec.pk, 'condition': 'cash', 'job': 'private',
            'credit_rank': 'A1', 'visit_result': 'bought', 'quantity': 1,
        })
        before = RecordUpdate.objects.filter(customer=self.customer, scope='case').count()
        # همان داده‌ها دوباره
        self.client.post(reverse('customers:case_save'), {
            'reception': rec.pk, 'condition': 'cash', 'job': 'private',
            'credit_rank': 'A1', 'visit_result': 'bought', 'quantity': 1,
        })
        after = RecordUpdate.objects.filter(customer=self.customer, scope='case').count()
        self.assertEqual(before, after, 'بدون تغییر نباید خط جدید ثبت شود')

    def test_updates_visible_in_page(self):
        rec = self._complete_reception()
        self.client.post(reverse('customers:case_save'), {
            'reception': rec.pk, 'condition': 'cash', 'job': 'private',
            'credit_rank': 'A1', 'visit_result': 'bought', 'quantity': 1,
        })
        self.client.post(reverse('customers:case_save'), {
            'reception': rec.pk, 'condition': 'cheque', 'cheque_owner': 'self', 'job': 'retired',
            'credit_rank': 'C1', 'visit_result': 'abandoned', 'quantity': 1,
        })
        body = self.client.get(f'{self.hub}?tab=case&c={self.customer.pk}').content.decode('utf-8')
        self.assertIn('تاریخچه تغییرات این فرد', body)
        self.assertIn('بازنشسته', body)
