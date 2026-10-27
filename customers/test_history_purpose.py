"""تست ماندگار: تاریخچه تماس — هدف و وضعیت برای تماس‌های غیرپیگیری."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from calls.models import Call
from customers.models import Customer


class CallHistoryPurposeStatusTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('hps_admin', password='t123456')
        cls.customer = Customer.objects.create(name='مشتری تاریخچه', mobile='09121470001',
                                               assigned_to=cls.user, created_by=cls.user)
        Call.objects.create(customer=cls.customer, caller_name=cls.customer.name,
                            call_number=cls.customer.mobile, call_type='incoming',
                            contact_type='incoming', purpose='support', status='busy',
                            notes='تماس جدید پشتیبانی', called_by=cls.user)
        Call.objects.create(customer=cls.customer, caller_name=cls.customer.name,
                            call_number=cls.customer.mobile, call_type='outgoing',
                            contact_type='followup', purpose='followup',
                            status='followup', notes='تماس پیگیری', called_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)
        body = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')
        start = body.find(f'id="calls-row-{self.customer.pk}"')
        end = body.find('<tr id="calls-row-', start + 10)
        if end == -1:
            end = body.find('</table>', start)
        self.section = body[start:end] if start != -1 else ''

    def test_purpose_shown_for_new_call(self):
        self.assertIn('پشتیبانی', self.section)
        self.assertIn('title="هدف تماس"', self.section)

    def test_status_shown_for_new_call(self):
        self.assertIn('مشغول', self.section)
        self.assertIn('title="وضعیت تماس"', self.section)

    def test_status_colors(self):
        self.assertIn('bg-amber-50 text-amber-700', self.section)  # busy

    def test_notes_still_shown(self):
        self.assertIn('تماس جدید پشتیبانی', self.section)
        self.assertIn('تماس پیگیری', self.section)

    def test_followup_call_keeps_type_badge(self):
        self.assertIn('پیگیری', self.section)
