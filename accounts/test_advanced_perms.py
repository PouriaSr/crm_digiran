"""تست ماندگار: مجوزهای پیشرفته برای قابلیت‌های جدید."""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserPermissionOverride
from accounts.permissions import (PERMISSIONS, PERMISSION_META, ROLE_SUPPORT,
                                  ROLE_TO_GROUP, has_permission)

NEW_KEYS = ('customers.profile_full', 'customers.registration', 'customers.history')
CLUB_KEYS = (
    'customers.club', 'customers.club_evaluate', 'customers.club_select',
    'customers.club_edit', 'customers.club_payment', 'customers.club_manage',
)


class AdvancedPermissionsTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('adv_admin', password='t123456')
        cls.support = User.objects.create_user('adv_support', password='t123456')
        cls.support.groups.add(Group.objects.get_or_create(
            name=ROLE_TO_GROUP[ROLE_SUPPORT])[0])

    def setUp(self):
        self.client.force_login(self.admin)

    # ── رجیستری ──
    def test_new_keys_registered_with_meta(self):
        for key in NEW_KEYS:
            self.assertIn(key, PERMISSIONS)
            self.assertIn(key, PERMISSION_META)
            self.assertIn(PERMISSION_META[key][0], ('مشتریان', 'تب‌های مرکز مشتریان'))

    def test_all_permissions_have_meta(self):
        self.assertEqual(set(PERMISSIONS), set(PERMISSION_META))

    # ── ماتریس ──
    def test_matrix_renders_all_keys(self):
        body = self.client.get(f'/accounts/users/{self.support.pk}/edit/').content.decode('utf-8')
        for key in PERMISSIONS:
            field = 'perm__' + key.replace('.', '_')
            self.assertIn(f'name="{field}"', body, f'{key} در ماتریس نیست')

    def test_matrix_labels_new_features(self):
        body = self.client.get(f'/accounts/users/{self.support.pk}/edit/').content.decode('utf-8')
        for label in ('پروفایل کامل مشتری', 'تب ثبت اطلاعات', 'تاریخچه تب‌ها'):
            self.assertIn(label, body)

    def test_club_pages_and_operations_are_editable_in_advanced_matrix(self):
        body = self.client.get(f'/accounts/users/{self.support.pk}/edit/').content.decode('utf-8')
        for key in CLUB_KEYS:
            self.assertIn(key, PERMISSIONS)
            self.assertIn(key, PERMISSION_META)
            field = 'perm__' + key.replace('.', '_')
            self.assertIn(f'name="{field}"', body, f'{key} در دسترسی پیشرفته نیست')
        for label in (
            'تب باشگاه مشتریان', 'ارزیابی و ارزیابی مجدد وام و گوشی',
            'ثبت قرارداد باشگاه', 'ویرایش و اعمال ارزیابی مجدد قرارداد باشگاه',
            'پرداخت‌های باشگاه', 'مدیریت طرح‌های وام',
        ):
            self.assertIn(label, body)

    # ── override ──
    def _save_with(self, **perms):
        data = {
            'username': self.support.username, 'first_name': 'پشتیبان',
            'last_name': 'تست', 'email': '', 'role': ROLE_SUPPORT, 'is_active': 'on',
        }
        for key in PERMISSIONS:
            data['perm__' + key.replace('.', '_')] = 'inherit'
        for key, val in perms.items():
            data['perm__' + key.replace('.', '_')] = val
        return self.client.post(f'/accounts/users/{self.support.pk}/edit/', data, follow=True)

    def test_override_allow_and_deny(self):
        self._save_with(customers_profile_full='allow',
                        customers_registration='allow',
                        customers_history='deny')
        self.support.refresh_from_db()
        self.assertTrue(has_permission(self.support, 'customers.profile_full'))
        self.assertTrue(has_permission(self.support, 'customers.registration'))
        self.assertFalse(has_permission(self.support, 'customers.history'))

    def test_club_switches_saved_from_advanced_page_are_effective(self):
        response = self._save_with(
            customers_club='allow', customers_club_evaluate='allow',
            customers_club_select='allow', customers_club_edit='deny',
            customers_club_payment='deny', customers_club_manage='deny',
        )
        self.assertEqual(response.status_code, 200)
        self.support.refresh_from_db()
        self.assertTrue(has_permission(self.support, 'customers.club'))
        self.assertTrue(has_permission(self.support, 'customers.club_evaluate'))
        self.assertTrue(has_permission(self.support, 'customers.club_select'))
        self.assertFalse(has_permission(self.support, 'customers.club_edit'))
        self.assertFalse(has_permission(self.support, 'customers.club_payment'))
        self.assertFalse(has_permission(self.support, 'customers.club_manage'))

    def test_override_affects_ui(self):
        self._save_with(customers_registration='allow', customers_reception='allow', customers_history='deny')
        c = self.client
        c.force_login(self.support)
        hub = c.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')
        self.assertIn('data-hub-tab="registration"', hub)
        rec = c.get(reverse('customers:hub') + '?tab=reception').content.decode('utf-8')
        self.assertNotIn('تاریخچه پذیرش‌ها', rec)

    def test_default_roles(self):
        self.assertEqual(set(PERMISSIONS['customers.registration']),
                         {'admin', 'sales_manager'})
        self.assertEqual(set(PERMISSIONS['customers.profile_full']),
                         {'admin', 'sales_manager'})
        self.assertIn('support', PERMISSIONS['customers.history'])
