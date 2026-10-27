"""تست ماندگار: جدول آخرین تماس‌ها در صفحه‌ی مشتری فقط گزارش است."""
from django.contrib.auth.models import User
from django.test import TestCase

from calls.models import Call
from customers.models import Customer


class CallHistoryReportOnlyTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('ro_admin', password='t123456')
        cls.customer = Customer.objects.create(name='مشتری گزارش', mobile='09121420001',
                                               assigned_to=cls.user, created_by=cls.user)
        Call.objects.create(customer=cls.customer, caller_name=cls.customer.name,
                            call_number=cls.customer.mobile, call_type='incoming',
                            contact_type='incoming', purpose='sale', status='answered',
                            notes='گزارش', called_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)
        self.body = self.client.get(f'/customers/{self.customer.pk}/').content.decode('utf-8')
        self.section = self.body[:self.body.find('آخرین فاکتورها')]

    def test_calls_table_has_no_details_link(self):
        start = self.body.find('آخرین تماس‌ها')
        section = self.body[start:self.body.find('آخرین فاکتورها')]
        self.assertNotIn('جزئیات', section)

    def test_no_call_detail_urls(self):
        start = self.body.find('آخرین تماس‌ها')
        section = self.body[start:self.body.find('آخرین فاکتورها')]
        self.assertNotIn('/calls/', section)

    def test_report_columns_present(self):
        start = self.body.find('آخرین تماس‌ها')
        section = self.body[start:self.body.find('آخرین فاکتورها')]
        for col in ('تاریخ', 'هدف', 'وضعیت', 'ثبت‌کننده'):
            self.assertIn(col, section)

    def test_call_action_button_still_present(self):
        self.assertIn('openQuickCall', self.body)

    def test_invoices_section_intact(self):
        self.assertIn('آخرین فاکتورها', self.body)
