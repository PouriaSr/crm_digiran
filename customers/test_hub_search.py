"""
تست جستجوی مرکز مشتریان (کامل و partial).

این تست جلوی بازگشت باگ واقعی را می‌گیرد: پس از حذف تب «تماس و پیگیری»،
خطی در بلوک جستجو به کوئری حذف‌شده `calls` ارجاع می‌داد و هر جستجو ۵۰۰ می‌شد.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from calls.models import Call
from customers.models import Customer


class HubSearchTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('search_admin', password='t123456')
        cls.customer = Customer.objects.create(
            name='مشتری جستجو', mobile='09121230001',
            assigned_to=cls.user, created_by=cls.user,
        )
        cls.other = Customer.objects.create(
            name='مشتری دیگر', mobile='09121230002',
            assigned_to=cls.user, created_by=cls.user,
        )
        Call.objects.create(customer=cls.customer, caller_name=cls.customer.name,
                            call_number=cls.customer.mobile, contact_type='incoming',
                            status='answered', called_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)
        self.hub = reverse('customers:hub')

    def test_search_by_mobile(self):
        # صفحه‌ی کامل، لیست همه‌ی مشتریان را در مودال انتخاب‌گر دارد؛
        # برای بررسی نتیجه‌ی جستجو، پاسخ partial (فقط جدول) را می‌سنجیم.
        r = self.client.get(
            f'{self.hub}?tab=info&partial=1&q=09121230001',
            headers={'HX-Request': 'true'},
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'مشتری جستجو')
        self.assertNotContains(r, 'مشتری دیگر')

    def test_search_by_partial_number(self):
        r = self.client.get(f'{self.hub}?tab=info&q=0912123')
        self.assertEqual(r.status_code, 200)

    def test_search_by_name(self):
        r = self.client.get(f'{self.hub}?tab=info&q=مشتری جستجو')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'مشتری جستجو')

    def test_search_no_result(self):
        r = self.client.get(f'{self.hub}?tab=info&q=zzzz-not-found')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'هیچ مشتری')

    def test_search_empty(self):
        r = self.client.get(f'{self.hub}?tab=info&q=')
        self.assertEqual(r.status_code, 200)

    def test_partial_search(self):
        """همان درخواستی که HTMX برای جستجوی زنده می‌فرستد"""
        r = self.client.get(
            f'{self.hub}?tab=info&partial=1&q=0912123',
            headers={'HX-Request': 'true', 'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, '<html', status_code=200)
        self.assertContains(r, 'customer-table-container')

    def test_partial_search_no_result(self):
        r = self.client.get(
            f'{self.hub}?tab=info&partial=1&q=zzzz',
            headers={'HX-Request': 'true'},
        )
        self.assertEqual(r.status_code, 200)

    def test_all_tabs_render_with_search(self):
        for tab in ('info', 'case', 'reception', 'invoice', 'followup', 'call', 'visit'):
            url = f'{self.hub}?tab={tab}&q=0912123'
            if tab in ('case', 'reception'):
                url += f'&c={self.customer.pk}'
            with self.subTest(tab=tab):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 200)


class NewCallButtonRuleTest(TestCase):
    """
    دکمه «ثبت تماس جدید»:
      فعال  → مشتری با آن نام/شماره وجود ندارد (یا جستجو خالی است)
      غیرفعال → مشتری پیدا شد
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('btn_admin', password='t123456')
        cls.customer = Customer.objects.create(
            name='مشتری موجود', mobile='09121235001',
            assigned_to=cls.user, created_by=cls.user,
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.hub = reverse('customers:hub')

    def _header(self, q):
        r = self.client.get(f'{self.hub}?tab=info&partial=1&q={q}',
                            headers={'HX-Request': 'true'})
        self.assertEqual(r.status_code, 200)
        return r.headers.get('X-Show-New-Customer')

    def test_disabled_when_search_empty(self):
        self.assertEqual(self._header(''), 'false')

    def test_enabled_when_no_match(self):
        self.assertEqual(self._header('zzzz-not-found'), 'true')

    def test_disabled_when_mobile_matches(self):
        self.assertEqual(self._header('09121235001'), 'false')

    def test_disabled_when_partial_mobile_matches(self):
        self.assertEqual(self._header('0912123'), 'false')

    def test_disabled_when_name_matches(self):
        self.assertEqual(self._header('مشتری موجود'), 'false')

    def test_initial_state_disabled_without_search(self):
        body = self.client.get(f'{self.hub}?tab=info').content.decode('utf-8')
        self.assertIn('showNewBtn: false', body)

    def test_initial_state_enabled_for_no_match(self):
        body = self.client.get(f'{self.hub}?tab=info&q=zzzz-nope').content.decode('utf-8')
        self.assertIn('showNewBtn: true', body)

    def test_initial_state_disabled_for_existing(self):
        body = self.client.get(f'{self.hub}?tab=info&q=09121235001').content.decode('utf-8')
        self.assertIn('showNewBtn: false', body)
