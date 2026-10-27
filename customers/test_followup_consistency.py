from datetime import timedelta
"""تست ماندگار: هم‌خوانی وضعیت پیگیری بین لیست، تاریخچه و مودال ویرایش."""
import jdatetime
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from calls.models import Call
from customers.models import Customer, FollowUp


def jdate(d):
    return jdatetime.date.fromgregorian(date=d).strftime('%Y/%m/%d')


class FollowUpConsistencyTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('fcs_admin', password='t123456')
        cls.customer = Customer.objects.create(name='مشتری پیگیری', mobile='09121500001',
                                               stage='potential', needs_followup=True,
                                               assigned_to=cls.user, created_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)

    def _followup_call(self, days=2):
        FollowUp.objects.create(customer=self.customer,
                                due_date=timezone.localdate())
        due = timezone.localdate() + timedelta(days=days)
        self.client.post(reverse('customers:quick_call', args=[self.customer.pk]), {
            'kind': 'followup', 'notes': 'نتیجه پیگیری',
            'follow_up_date': jdate(timezone.localdate()),
        })
        return Call.objects.filter(customer=self.customer, contact_type='followup').order_by('-id').first()

    # ── ثبت ──
    def test_followup_call_marks_is_followed_up(self):
        call = self._followup_call()
        self.assertIsNotNone(call)
        self.assertTrue(call.is_followed_up)
        self.assertIsNotNone(call.follow_up_date)

    # ── نمایش ──
    def test_modal_data_reflects_done(self):
        call = self._followup_call()
        body = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')
        self.assertIn(f'data-call-id="{call.pk}"', body)
        idx = body.find(f'data-call-id="{call.pk}"')
        chunk = body[idx:idx + 1200]
        self.assertIn('data-call-fu-done="1"', chunk)

    def test_history_shows_done_chip(self):
        self._followup_call()
        body = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')
        self.assertIn('پیگیری انجام شد', body)

    # ── ویرایش: برداشتن تیک → بازگشایی ──
    def test_unchecking_reopens_followup(self):
        call = self._followup_call()
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.needs_followup)

        self.client.post(reverse('customers:hub_call_edit', args=[call.pk]), {
            'notes': 'اصلاح شد', 'follow_up_date': jdate(timezone.localdate()),
            # بدون is_followed_up
        })
        call.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertFalse(call.is_followed_up)
        self.assertTrue(FollowUp.objects.filter(customer=self.customer, is_done=False).exists())
        self.assertTrue(self.customer.needs_followup)

    def test_checking_closes_followup(self):
        call = self._followup_call()
        FollowUp.objects.create(customer=self.customer, due_date=timezone.localdate())
        self.client.post(reverse('customers:hub_call_edit', args=[call.pk]), {
            'notes': 'انجام شد', 'follow_up_date': jdate(timezone.localdate()),
            'is_followed_up': '1',
        })
        call.refresh_from_db()
        self.assertTrue(call.is_followed_up)
        self.assertEqual(FollowUp.objects.filter(customer=self.customer, is_done=False).count(), 0)
