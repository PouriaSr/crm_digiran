"""تست ماندگار: سطوح دسترسی و ماتریس پیشرفته پس از اصلاحات."""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from accounts.permissions import (PERMISSIONS, PERMISSION_META, ROLE_OPERATOR,
                                  ROLE_SALES_MANAGER, ROLE_SUPPORT, ROLE_TO_GROUP,
                                  has_permission)
from customers.models import Customer


class PermissionsAuditTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('pa_admin', password='t123456')
        cls.mgr = User.objects.create_user('pa_mgr', password='t123456')
        cls.mgr.groups.add(Group.objects.get_or_create(
            name=ROLE_TO_GROUP[ROLE_SALES_MANAGER])[0])
        cls.sup = User.objects.create_user('pa_sup', password='t123456')
        cls.sup.groups.add(Group.objects.get_or_create(
            name=ROLE_TO_GROUP[ROLE_SUPPORT])[0])
        cls.customer = Customer.objects.create(name='مشتری دسترسی', mobile='09121520001',
                                               assigned_to=cls.admin, created_by=cls.admin)

    def setUp(self):
        self.client.force_login(self.admin)

    # ── رجیستری ──
    def test_visit_permission_removed(self):
        self.assertNotIn('customers.visit', PERMISSIONS)
        self.assertNotIn('customers.visit', PERMISSION_META)

    def test_registry_consistent(self):
        self.assertEqual(set(PERMISSIONS), set(PERMISSION_META))

    # ── ماتریس پیشرفته ──
    def test_matrix_on_edit_form(self):
        body = self.client.get(f'/accounts/users/{self.sup.pk}/edit/').content.decode('utf-8')
        for key in PERMISSIONS:
            self.assertIn(f'name="perm__{key.replace(".", "_")}"', body)

    def test_matrix_on_create_form(self):
        body = self.client.get('/accounts/users/new/').content.decode('utf-8')
        for key in PERMISSIONS:
            self.assertIn(f'name="perm__{key.replace(".", "_")}"', body)

    # ── غیرفعال‌سازی با مجوز ──
    def test_manager_can_deactivate(self):
        self.client.force_login(self.mgr)
        self.client.post(reverse('customers:deactivate', args=[self.customer.pk]))
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_deleted)

    def test_manager_can_restore(self):
        self.client.force_login(self.mgr)
        self.client.post(reverse('customers:deactivate', args=[self.customer.pk]))
        self.client.post(reverse('customers:restore', args=[self.customer.pk]))
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_deleted)

    def test_support_cannot_deactivate(self):
        self.client.force_login(self.sup)
        r = self.client.post(reverse('customers:deactivate', args=[self.customer.pk]))
        self.customer.refresh_from_db()
        self.assertEqual(r.status_code, 403)
        self.assertFalse(self.customer.is_deleted)

    def test_override_can_grant_delete_permission(self):
        from accounts.models import UserPermissionOverride
        UserPermissionOverride.objects.create(user=self.sup,
                                              permission_key='customers.delete',
                                              granted=True)
        self.assertTrue(has_permission(self.sup, 'customers.delete'))

    # ── لیست غیرفعال‌ها ──
    def test_inactive_list_requires_view_permission(self):
        self.client.force_login(self.sup)
        r = self.client.get('/customers/inactive/')
        self.assertEqual(r.status_code, 200)

    def test_user_without_view_cannot_open_inactive_list(self):
        outsider = User.objects.create_user('pa_outsider', password='t123456')
        self.client.force_login(outsider)
        r = self.client.get('/customers/inactive/')
        self.assertEqual(r.status_code, 403)
