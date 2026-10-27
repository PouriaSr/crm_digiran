"""تست ماندگار: صفحه‌ی مشتری از فرم سبز (quick call) برای ثبت تماس استفاده می‌کند."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from calls.models import Call
from customers.models import Customer


class DetailUsesQuickCallModalTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('gq_admin', password='t123456')
        cls.customer = Customer.objects.create(name='علی کشاورز', mobile='09121410001',
                                               assigned_to=cls.user, created_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)
        self.body = self.client.get(f'/customers/{self.customer.pk}/').content.decode('utf-8')

    # ── فرم سبز ──
    def test_green_modal_included(self):
        self.assertIn('id="qc-backdrop"', self.body)
        self.assertIn('id="qc-title"', self.body)

    def test_buttons_use_quick_call(self):
        self.assertIn(f"openQuickCall('new', {self.customer.pk}", self.body)

    def test_no_button_calls_blue_modal(self):
        self.assertNotIn('onclick="openCallModalFor', self.body)

    def test_quick_modal_has_next(self):
        self.assertIn('id="qc-next"', self.body)

    # ── ثبت و بازگشت ──
    def test_submit_new_call_returns_to_customer(self):
        before = Call.objects.filter(customer=self.customer).count()
        r = self.client.post(reverse('customers:quick_call', args=[self.customer.pk]), {
            'kind': 'new', 'notes': 'تماس از صفحه مشتری',
            'next': f'/customers/{self.customer.pk}/',
        })
        self.customer.refresh_from_db()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Call.objects.filter(customer=self.customer).count(), before + 1)
        self.assertEqual(self.customer.notes, 'تماس از صفحه مشتری')
        self.assertEqual(r.headers['Location'], f'/customers/{self.customer.pk}/')

    def test_invalid_next_blocked(self):
        r = self.client.post(reverse('customers:quick_call', args=[self.customer.pk]), {
            'kind': 'new', 'notes': 'تست امنیت', 'next': '//evil.com',
        })
        self.assertEqual(r.headers['Location'], '/customers/hub/?tab=info')

    def test_submit_without_next_goes_to_hub(self):
        r = self.client.post(reverse('customers:quick_call', args=[self.customer.pk]), {
            'kind': 'new', 'notes': 'بدون next',
        })
        self.assertEqual(r.headers['Location'], '/customers/hub/?tab=info')
