"""تست ماندگار: اعمال آنی دسترسی‌ها و هدرهای بدون کش."""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserPermissionOverride
from accounts.permissions import ROLE_SALES, ROLE_TO_GROUP, has_permission
from customers.models import Customer


class LivePermissionTest(TestCase):
    """تغییر دسترسی یا انتقال مشتری، همان درخواست بعدی اعمال می‌شود"""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('live_admin', password='t123456')
        cls.user = User.objects.create_user('live_user', password='t123456')
        cls.user.groups.add(Group.objects.get_or_create(
            name=ROLE_TO_GROUP[ROLE_SALES])[0])
        cls.other = User.objects.create_user('live_other', password='t123456',
                                             first_name='کارمند', last_name='جدید')
        cls.customer = Customer.objects.create(
            name='مشتری زنده', mobile='09121340001', national_id='0012345678',
            address='تهران', assigned_to=cls.admin, created_by=cls.admin)

    def setUp(self):
        self.client.force_login(self.user)

    # ── اعمال آنی دسترسی ──
    def test_grant_override_applies_immediately(self):
        body = self.client.get(f'/customers/{self.customer.pk}/').content.decode('utf-8')
        self.assertNotIn('اطلاعات تماس', body)

        UserPermissionOverride.objects.create(
            user=self.user, permission_key='customers.profile_full', granted=True)

        body2 = self.client.get(f'/customers/{self.customer.pk}/').content.decode('utf-8')
        self.assertIn('اطلاعات تماس', body2)

    def test_revoke_override_applies_immediately(self):
        UserPermissionOverride.objects.create(
            user=self.user, permission_key='customers.profile_full', granted=True)
        self.client.get(f'/customers/{self.customer.pk}/')

        UserPermissionOverride.objects.filter(
            user=self.user, permission_key='customers.profile_full').update(granted=False)

        body = self.client.get(f'/customers/{self.customer.pk}/').content.decode('utf-8')
        self.assertNotIn('اطلاعات تماس', body)

    def test_no_session_caching_of_permissions(self):
        self.assertFalse(has_permission(self.user, 'customers.profile_full'))
        UserPermissionOverride.objects.create(
            user=self.user, permission_key='customers.profile_full', granted=True)
        self.assertTrue(has_permission(self.user, 'customers.profile_full'))

    # ── انتقال ──
    def test_transfer_visible_immediately(self):
        self.client.post(reverse('customers:reassign', args=[self.customer.pk]),
                         {'assigned_to': self.other.pk, 'next': 'hub'})
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.assigned_to_id, self.other.pk)

        body = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')
        self.assertIn('کارمند جدید', body)

    # ── هدرها ──
    def test_pages_are_no_store(self):
        for url in (reverse('customers:hub') + '?tab=info',
                    f'/customers/{self.customer.pk}/',
                    f'/customers/{self.customer.pk}/edit/?is_modal=1'):
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertIn('no-store', (r.headers.get('Cache-Control') or '').lower())
                self.assertIn('cookie', (r.headers.get('Vary') or '').lower())

    def test_htmx_partial_no_store(self):
        r = self.client.get(reverse('customers:hub') + '?tab=info',
                            headers={'HX-Request': 'true'})
        self.assertIn('no-store', (r.headers.get('Cache-Control') or '').lower())

    def test_partial_does_not_leak_profile(self):
        r = self.client.get(reverse('customers:hub') + '?tab=info',
                            headers={'HX-Request': 'true'})
        self.assertNotIn('0012345678', r.content.decode('utf-8'))
