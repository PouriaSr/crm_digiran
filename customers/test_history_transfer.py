"""تست ماندگار: تاریخچه بازشوی تماس + انتقال مشتری."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from calls.models import Call
from customers.models import Customer


class CustomerHistoryAndTransferTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('hist_admin', password='t123456')
        cls.other = User.objects.create_user('hist_other', password='t123456',
                                             first_name='کارمند', last_name='دوم')
        cls.customer = Customer.objects.create(name='مشتری تاریخچه', mobile='09121250001',
                                               stage='potential', needs_followup=True,
                                               assigned_to=cls.admin, created_by=cls.admin)
        Call.objects.create(customer=cls.customer, caller_name=cls.customer.name,
                            call_number=cls.customer.mobile, contact_type='incoming',
                            status='answered', notes='تماس اولیه', called_by=cls.admin)
        Call.objects.create(customer=cls.customer, caller_name=cls.customer.name,
                            call_number=cls.customer.mobile, contact_type='followup',
                            status='followup', notes='پیگیری بعدی', called_by=cls.admin)

    def setUp(self):
        self.client.force_login(self.admin)
        self.hub = reverse('customers:hub')

    # ── تاریخچه ──
    def test_history_toggle_present(self):
        body = self.client.get(f'{self.hub}?tab=info').content.decode('utf-8')
        self.assertIn(f'toggleCustomerCalls({self.customer.pk}', body)
        self.assertIn(f'id="calls-row-{self.customer.pk}"', body)

    def test_history_lists_all_calls(self):
        body = self.client.get(f'{self.hub}?tab=info').content.decode('utf-8')
        self.assertIn('تماس اولیه', body)
        self.assertIn('پیگیری بعدی', body)
        self.assertIn('تاریخچه تماس‌ها (۲ مورد)', body)

    def test_history_no_calls_message(self):
        empty = Customer.objects.create(name='بدون تماس', mobile='09121250002',
                                        assigned_to=self.admin, created_by=self.admin)
        body = self.client.get(f'{self.hub}?tab=info').content.decode('utf-8')
        self.assertIn(f'id="calls-row-{empty.pk}"', body)
        self.assertIn('هنوز تماسی برای این مشتری ثبت نشده است', body)

    # ── انتقال ──
    def test_transfer_button_present(self):
        body = self.client.get(f'{self.hub}?tab=info').content.decode('utf-8')
        self.assertIn(f'openReassignModal({self.customer.pk}', body)
        self.assertIn('id="reassign-backdrop"', body)

    def test_transfer_changes_assignee(self):
        self.client.post(reverse('customers:reassign', args=[self.customer.pk]),
                         {'assigned_to': self.other.pk, 'next': 'hub'})
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.assigned_to_id, self.other.pk)

    def test_transfer_returns_to_hub(self):
        r = self.client.post(reverse('customers:reassign', args=[self.customer.pk]),
                             {'assigned_to': self.other.pk, 'next': 'hub'})
        self.assertEqual(r.status_code, 302)
        self.assertIn('/customers/hub/', r.headers['Location'])

    def test_transfer_requires_permission(self):
        outsider = User.objects.create_user('hist_outsider', password='t123456')
        self.client.force_login(outsider)
        r = self.client.post(reverse('customers:reassign', args=[self.customer.pk]),
                             {'assigned_to': self.other.pk})
        self.assertEqual(r.status_code, 403)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.assigned_to_id, self.admin.pk)
