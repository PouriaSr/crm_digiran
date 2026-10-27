"""تست ماندگار: جدول مشتریان ستون «شرح مکالمه» ندارد؛ شرح در تاریخچه است."""
import re

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from calls.models import Call
from customers.models import Customer


class NotesColumnRemovedTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('ncr_admin', password='t123456')
        cls.customer = Customer.objects.create(name='مشتری ستون', mobile='09121460001',
                                               assigned_to=cls.user, created_by=cls.user,
                                               notes='شرح کلی مشتری')
        Call.objects.create(customer=cls.customer, caller_name=cls.customer.name,
                            call_number=cls.customer.mobile, call_type='incoming',
                            contact_type='incoming', purpose='sale', status='answered',
                            notes='شرح داخل تماس', called_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)
        self.body = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')
        m = re.search(r'<thead[^>]*>.*?</thead>', self.body, re.S)
        self.header = m.group(0) if m else ''

    # ── جدول ──
    def test_notes_column_removed(self):
        self.assertNotIn('شرح مکالمه', self.header)

    def test_seven_columns(self):
        ths = re.findall(r'<th[ >][^>]*>(.*?)</th>', self.header, re.S)
        self.assertEqual(len(ths), 7)

    def test_expected_columns(self):
        for col in ('نام مشتری', 'شماره تماس', 'منبع جذب', 'وضعیت پیگیری',
                    'کارمند مسئول', 'تاریخ ثبت', 'عملیات'):
            self.assertIn(col, self.header)

    # ── تاریخچه ──
    def test_notes_shown_in_history(self):
        self.assertIn('شرح داخل تماس', self.body)

    def test_history_row_colspan_matches(self):
        self.assertIn('colspan="7"', self.body)
        self.assertNotIn('colspan="8"', self.body)
