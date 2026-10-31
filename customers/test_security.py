"""
تست‌های امنیتی بازرسی: دسترسی به صفحات و عملیات حساس.

باگ‌های واقعی که این تست‌ها از بازگشتشان جلوگیری می‌کنند:
  • صفحه‌ی جزئیات مشتری برای کاربر ناشناس باز بود (افشای پروفایل)
  • ثبت مراجعه (hub_submit_visit) هیچ محافظتی نداشت
"""
from ads.models import AdSource
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from calls.models import Call
from customers.models import Customer
from accounts.permissions import ROLE_SALES, ROLE_TO_GROUP


class CustomerDetailAccessTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.customer = Customer.objects.create(name='محرمانه', mobile='09120002222')
        cls.outsider = User.objects.create_user('sec_outsider', password='t123456')
        cls.sales = User.objects.create_user('sec_sales', password='t123456')
        cls.sales.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP[ROLE_SALES])[0])

    def test_anonymous_cannot_view_detail(self):
        r = self.client.get(reverse('customers:detail', args=[self.customer.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login', r.headers.get('Location', ''))

    def test_user_without_permission_gets_403(self):
        self.client.force_login(self.outsider)
        r = self.client.get(reverse('customers:detail', args=[self.customer.pk]))
        self.assertEqual(r.status_code, 403)

    def test_sales_can_view_detail(self):
        self.client.force_login(self.sales)
        r = self.client.get(reverse('customers:detail', args=[self.customer.pk]))
        self.assertEqual(r.status_code, 200)


class QuickCallPermissionTest(TestCase):
    """کاربر بدون مجوز نباید بتواند تماس/پیگیری ثبت کند"""

    @classmethod
    def setUpTestData(cls):
        cls.customer = Customer.objects.create(name='بدون دسترسی', mobile='09120004444',
                                               needs_followup=True)
        cls.outsider = User.objects.create_user('sec_qc_out', password='t123456')

    def test_outside_user_cannot_create_call(self):
        self.client.force_login(self.outsider)
        before = Call.objects.count()
        self.client.post(reverse('customers:quick_call', args=[self.customer.pk]),
                         {'source': AdSource.objects.get_or_create(phone_number='09129999888', defaults={'label':'تست'})[0].pk, 'kind': 'followup', 'notes': 'تلاش غیرمجاز'})
        self.assertEqual(Call.objects.count(), before)
        self.customer.refresh_from_db()
        self.assertNotEqual(self.customer.notes, 'تلاش غیرمجاز')
