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

    def test_column_order(self):
        ths = re.findall(r'<th[ >][^>]*>(.*?)</th>', self.section, re.S)
        labels = [re.sub(r'<[^>]+>', '', t).strip() for t in ths]
        self.assertEqual(labels[:7],
                         ['تاریخ', 'تاریخ پیگیری', 'نوع', 'هدف',
                          'وضعیت', 'شرح مکالمه', 'کارمند'])
        # ستون آخر (ویرایش) بدون عنوان است
        self.assertLessEqual(len(labels), 8)

    def test_notes_value_rendered(self):
        self.assertIn('مشتری درباره گارانتی سوال داشت', self.section)

    def test_empty_notes_show_dash(self):
        self.assertIn('—', self.section)

    def test_still_no_details_link(self):
        self.assertNotIn('/calls/', self.section)
