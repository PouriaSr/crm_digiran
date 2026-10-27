"""Regression tests for v12 fixes"""
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from customers.models import Customer
from ads.models import AdSource


class CustomerCreateAssignedToTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('reg_a', password='t123456')
        cls.sales2 = User.objects.create_user('reg_s2', password='t123456')

    def test_create_respects_selected_assignee(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('customers:create'), {
            'name': 'مشتری با مسئول مشخص',
            'mobile': '09129999001',
            'status': 'lead',
            'source': 'direct',
            'assigned_to': self.sales2.pk,
            'notes': 'تست',
        })
        c = Customer.objects.filter(mobile='09129999001').first()
        self.assertIsNotNone(c, "customer باید ساخته بشه")
        self.assertEqual(c.assigned_to, self.sales2,
                         "assigned_to انتخابی باید حفظ بشه")


class HubSubmitCallAdSourceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('hub_a', password='t123456')
        cls.source = AdSource.objects.create(phone_number='09129999999', label='تست')

    def test_hub_call_saves_ad_source(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('customers:hub_submit_call'), {
            'mobile': '09129999002',
            'name': 'مشتری از آگهی',
            'call_type': 'incoming',
            'source': str(self.source.pk),
            'customer_type': 'none',
            'status': 'active',
            'notes': 'تست',
            'follow_up_time': '10:30', 'follow_up_date': '',
            'installments_count': '',
            'cheques_count': '',
        })
        c = Customer.objects.filter(mobile='09129999002').first()
        self.assertIsNotNone(c, "customer باید ساخته بشه")
        self.assertEqual(c.ad_source, self.source,
                         "ad_source باید ذخیره بشه")
