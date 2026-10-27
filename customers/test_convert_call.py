"""تست ماندگار: تبدیل تماس عادی به پیگیری از مودال ویرایش + رفع escapejs."""
from datetime import timedelta

import jdatetime
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from calls.models import Call
from customers.models import Customer, FollowUp


def jdate(d):
    return jdatetime.date.fromgregorian(date=d).strftime('%Y/%m/%d')


class ConvertCallToFollowUpTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('ccf_admin', password='t123456')
        cls.customer = Customer.objects.create(name='مشتری تبدیل', mobile='09121530001',
                                               assigned_to=cls.user, created_by=cls.user)
        cls.call = Call.objects.create(
            customer=cls.customer, caller_name=cls.customer.name,
            call_number=cls.customer.mobile, call_type='incoming',
            contact_type='incoming', purpose='sale', status='answered',
            notes='تستی - با خط تیره', called_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)

    # ── رفع باگ escapejs ──
    def test_notes_not_unicode_escaped_in_attributes(self):
        body = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')
        self.assertNotIn('\\u002D', body)
        self.assertIn('تستی - با خط تیره', body)

    # ── مودال ──
    def test_modal_has_needs_followup_checkbox(self):
        body = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')
        self.assertIn('id="ce-needs-followup"', body)
        self.assertIn('id="ce-need-date"', body)
        self.assertIn('data-jdp', body)

    # ── تبدیل ──
    def test_convert_to_followup(self):
        due = timezone.localdate() + timedelta(days=9)
        r = self.client.post(reverse('customers:hub_call_edit', args=[self.call.pk]), {
            'notes': 'تستی - با خط تیره',
            'needs_followup': '1',
            'needs_followup_time': '10:30', 'needs_followup_date': jdate(due),
        })
        self.call.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.call.contact_type, 'followup')
        self.assertEqual(self.call.call_type, 'outgoing')
        self.assertEqual(self.call.purpose, 'followup')
        self.assertEqual(self.call.status, 'followup')
        self.assertEqual(self.call.follow_up_date, due)
        self.assertFalse(self.call.is_followed_up)
        self.assertTrue(FollowUp.objects.filter(customer=self.customer, is_done=False).exists())
        self.assertTrue(self.customer.needs_followup)
        self.assertEqual(self.customer.stage, 'potential')

    def test_convert_requires_date(self):
        r = self.client.post(reverse('customers:hub_call_edit', args=[self.call.pk]), {
            'notes': 'بدون تاریخ', 'needs_followup': '1', 'needs_followup_time': '10:30', 'needs_followup_date': '',
        })
        self.call.refresh_from_db()
        self.assertEqual(self.call.contact_type, 'incoming')
        self.assertEqual(r.status_code, 302)

    def test_without_check_stays_normal(self):
        self.client.post(reverse('customers:hub_call_edit', args=[self.call.pk]), {
            'notes': 'ویرایش معمولی', 'status': 'missed', 'purpose': 'support',
        })
        self.call.refresh_from_db()
        self.assertEqual(self.call.contact_type, 'incoming')
        self.assertEqual(self.call.status, 'missed')
