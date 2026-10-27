"""تست ماندگار: نمایش شرح مکالمه در صفحه‌ی مشتری."""
import re

from django.contrib.auth.models import User
from django.test import TestCase

from calls.models import Call
from customers.models import Customer


class DetailNotesColumnTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('dnc_admin', password='t123456')
        cls.customer = Customer.objects.create(name='مشتری شرح', mobile='09121480001',
                                               assigned_to=cls.user, created_by=cls.user)
        Call.objects.create(customer=cls.customer, caller_name=cls.customer.name,
                            call_number=cls.customer.mobile, call_type='incoming',
                            contact_type='incoming', purpose='support', status='busy',
                            notes='مشتری درباره گارانتی سوال داشت', called_by=cls.user)
        Call.objects.create(customer=cls.customer, caller_name=cls.customer.name,
                            call_number=cls.customer.mobile, call_type='outgoing',
                            contact_type='followup', purpose='followup',
                            status='followup', notes='', called_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)
        body = self.client.get(f'/customers/{self.customer.pk}/').content.decode('utf-8')
        start = body.find('آخرین تماس‌ها')
        end = body.find('آخرین فاکتورها')
        self.section = body[start:end]

    def test_notes_column_present(self):
        self.assertIn('شرح مکالمه', self.section)

    def test_history_cards_have_call_context(self):
        self.assertEqual(self.section.count('<article '), 2)
        for text in ('هدف:', 'وضعیت:', 'ثبت‌کننده:', 'تماس مشتری', 'پیگیری'):
            self.assertIn(text, self.section)
        self.assertIn('title="تاریخ و ساعت ثبت"', self.section)

    def test_notes_value_rendered(self):
        self.assertIn('مشتری درباره گارانتی سوال داشت', self.section)

    def test_empty_notes_show_dash(self):
        self.assertIn('شرحی ثبت نشده است.', self.section)

    def test_still_no_details_link(self):
        self.assertNotIn('/calls/', self.section)
