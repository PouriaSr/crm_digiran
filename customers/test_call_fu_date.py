"""تست ماندگار: نمایش تاریخ پیگیری هر تماس در تاریخچه و جدول آخرین تماس‌ها."""
import re
from datetime import timedelta

import jdatetime
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from calls.models import Call
from customers.models import Customer

FA = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


def jdate(d):
    return jdatetime.date.fromgregorian(date=d).strftime('%Y/%m/%d')


class CallFollowUpDateDisplayTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('cfd_admin', password='t123456')
        cls.customer = Customer.objects.create(name='مشتری تاریخ', mobile='09121510001',
                                               assigned_to=cls.user, created_by=cls.user)
        cls.fu_day = timezone.localdate() + timedelta(days=5)
        Call.objects.create(customer=cls.customer, caller_name=cls.customer.name,
                            call_number=cls.customer.mobile, call_type='outgoing',
                            contact_type='followup', purpose='followup',
                            status='followup', notes='پیگیری دستی',
                            follow_up_date=cls.fu_day, is_followed_up=True,
                            called_by=cls.user)
        Call.objects.create(customer=cls.customer, caller_name=cls.customer.name,
                            call_number=cls.customer.mobile, call_type='incoming',
                            contact_type='incoming', purpose='sale', status='answered',
                            notes='بدون تاریخ پیگیری', called_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)
        self.hub = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')
        self.detail = self.client.get(f'/customers/{self.customer.pk}/').content.decode('utf-8')
        self.fu_fa = jdate(self.fu_day).translate(FA)

    # ── تاریخچه ──
    def test_history_shows_followup_date_chip(self):
        self.assertIn('title="تاریخ پیگیری"', self.hub)
        self.assertIn(self.fu_fa, self.hub)

    # ── صفحه مشتری ──
    def test_detail_has_followup_date_column(self):
        self.assertIn('تاریخ پیگیری', self.detail)
        self.assertIn(self.fu_fa, self.detail)

    def test_detail_column_order(self):
        theads = re.findall(r'<thead[^>]*>.*?</thead>', self.detail, re.S)
        head = next((t for t in theads if 'تاریخ پیگیری' in t), '')
        labels = [re.sub(r'<[^>]+>', '', x).strip()
                  for x in re.findall(r'<th[ >][^>]*>(.*?)</th>', head, re.S)]
        labels = [l for l in labels if l]
        self.assertEqual(labels[:4], ['تاریخ', 'تاریخ پیگیری', 'نوع', 'هدف'])

    def test_empty_followup_date_shows_dash(self):
        self.assertIn('text-gray-300', self.detail)
