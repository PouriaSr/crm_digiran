"""تست ماندگار: صفحه‌ی جزئیات مشتری فقط یک دکمه‌ی بازگشت دارد."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer


class DetailBackButtonTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('back_admin', password='t123456')
        cls.customer = Customer.objects.create(name='مشتری بازگشت', mobile='09121260003',
                                               assigned_to=cls.user, created_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)
        self.body = self.client.get(
            reverse('customers:detail', args=[self.customer.pk])).content.decode('utf-8')

    def test_single_back_button(self):
        self.assertEqual(self.body.count('بازگشت به لیست مشتریان'), 1)

    def test_old_buttons_removed(self):
        self.assertNotIn('بازگشت به لیست اطلاعات', self.body)
        self.assertNotIn('بازگشت به تماس و پیگیری', self.body)

    def test_back_link_targets_info_tab(self):
        self.assertIn(f'href="/customers/hub/?tab=info"', self.body)

    def test_no_legacy_call_tab_links(self):
        self.assertNotIn('?tab=call', self.body)

    def test_action_buttons_intact(self):
        for label in ('ثبت تماس', 'صدور فاکتور', 'ویرایش'):
            self.assertIn(label, self.body)
