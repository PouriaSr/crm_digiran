"""تست ماندگار: چرخه پیگیری (تاریخ، باز/انجام‌شده، پیگیری جدید)."""
from datetime import timedelta

import jdatetime
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from customers.models import Customer, FollowUp


def jdate(d):
    return jdatetime.date.fromgregorian(date=d).strftime('%Y/%m/%d')


class FollowUpCycleTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('fu_admin', password='t123456')

    def setUp(self):
        self.client.force_login(self.user)
        self.hub = reverse('customers:hub')

    def _create_with_followup(self, mobile='09121350001', days=3):
        due = timezone.localdate() + timedelta(days=days)
        self.client.post(reverse('customers:hub_submit_call'), {
            'mobile': mobile, 'name': 'مشتری پیگیری', 'call_type': 'incoming',
            'notes': 'نیاز به پیگیری', 'needs_followup': 'on',
            'follow_up_time': '10:30', 'follow_up_date': jdate(due),
        })
        customer = Customer.objects.filter(mobile=mobile).first()
        return customer, due

    # ── ساخت ──
    def test_call_with_followup_creates_open_record(self):
        customer, due = self._create_with_followup()
        fu = FollowUp.objects.filter(customer=customer).first()
        self.assertIsNotNone(fu)
        self.assertFalse(fu.is_done)
        self.assertEqual(fu.due_date, due)

    def test_followup_requires_date(self):
        mobile = '09121350009'
        self.client.post(reverse('customers:hub_submit_call'), {
            'mobile': mobile, 'name': 'بدون تاریخ', 'call_type': 'incoming',
            'notes': 'تست', 'needs_followup': 'on', 'follow_up_time': '10:30', 'follow_up_date': '',
        })
        self.assertFalse(FollowUp.objects.filter(customer__mobile=mobile).exists())

    # ── نمایش ──
    def test_list_shows_open_badge(self):
        self._create_with_followup()
        body = self.client.get(f'{self.hub}?tab=info').content.decode('utf-8')
        self.assertIn('وضعیت پیگیری', body)
        self.assertIn('● باز', body)

    def test_list_shows_none_for_customer_without_followup(self):
        Customer.objects.create(name='بدون پیگیری', mobile='09121350010',
                                assigned_to=self.user, created_by=self.user)
        body = self.client.get(f'{self.hub}?tab=info').content.decode('utf-8')
        self.assertIn('>---<', body)

    # ── بستن ──
    def test_followup_call_closes_record(self):
        customer, _ = self._create_with_followup()
        self.client.post(reverse('customers:quick_call', args=[customer.pk]), {
            'kind': 'followup', 'notes': 'نتیجه ثبت شد',
            'follow_up_time': '10:30', 'follow_up_date': jdate(timezone.localdate()),
        })
        customer.refresh_from_db()
        fu = FollowUp.objects.get(customer=customer)
        self.assertTrue(fu.is_done)
        self.assertIsNotNone(fu.done_at)
        self.assertFalse(customer.needs_followup)

        body = self.client.get(f'{self.hub}?tab=info').content.decode('utf-8')
        self.assertIn('✓ انجام شد', body)

    def test_followup_call_with_next_creates_new_open(self):
        customer, _ = self._create_with_followup()
        next_due = timezone.localdate() + timedelta(days=10)
        self.client.post(reverse('customers:quick_call', args=[customer.pk]), {
            'kind': 'followup', 'notes': 'پیگیری بعدی',
            'follow_up_time': '10:30', 'follow_up_date': jdate(timezone.localdate()),
            'needs_next': '1', 'next_follow_up_time': '10:30', 'next_follow_up_date': jdate(next_due),
        })
        customer.refresh_from_db()
        open_fu = FollowUp.objects.filter(customer=customer, is_done=False).first()
        self.assertIsNotNone(open_fu)
        self.assertEqual(open_fu.due_date, next_due)
        self.assertTrue(customer.needs_followup)

    def test_next_followup_requires_date(self):
        customer, _ = self._create_with_followup()
        before = FollowUp.objects.filter(customer=customer, is_done=False).count()
        self.client.post(reverse('customers:quick_call', args=[customer.pk]), {
            'kind': 'followup', 'notes': 'بدون تاریخ بعدی',
            'follow_up_time': '10:30', 'follow_up_date': jdate(timezone.localdate()),
            'needs_next': '1', 'next_follow_up_time': '10:30', 'next_follow_up_date': '',
        })
        # چون تاریخ بعدی نداشت، عملیات رد شد و پیگیری باز قبلی دست‌نخورده ماند
        self.assertEqual(FollowUp.objects.filter(customer=customer, is_done=False).count(), before)

    def test_followup_call_requires_date(self):
        customer, _ = self._create_with_followup()
        r = self.client.post(reverse('customers:quick_call', args=[customer.pk]), {
            'kind': 'followup', 'notes': 'بدون تاریخ',
        })
        self.assertEqual(r.status_code, 302)
        fu = FollowUp.objects.get(customer=customer)
        self.assertFalse(fu.is_done)
