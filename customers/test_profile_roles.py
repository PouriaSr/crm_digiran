"""تست ماندگار: پروفایل کامل فقط مدیر کل و مدیر فروش."""
from django.contrib.auth.models import Group, User
from django.test import TestCase

from accounts.permissions import (PERMISSIONS, ROLE_ACCOUNTANT, ROLE_ADS_MANAGER,
                                  ROLE_OPERATOR, ROLE_SALES, ROLE_SALES_MANAGER,
                                  ROLE_SUPPORT, ROLE_TO_GROUP, has_permission)
from customers.models import Customer


class ProfileFullRoleTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('pfr_admin', password='t123456')
        cls.customer = Customer.objects.create(
            name='مشتری آزمون', mobile='09121330001', national_id='0012345678',
            address='تهران', assigned_to=cls.admin, created_by=cls.admin)

        cls.users = {}
        for role in (ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_OPERATOR,
                     ROLE_ACCOUNTANT, ROLE_ADS_MANAGER):
            u = User.objects.create_user(f'pfr_{role}', password='t123456')
            u.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP[role])[0])
            cls.users[role] = u

    def test_only_admin_and_manager_have_permission(self):
        self.assertEqual(set(PERMISSIONS['customers.profile_full']),
                         {'admin', 'sales_manager'})

    def test_manager_sees_full_profile(self):
        self.client.force_login(self.users[ROLE_SALES_MANAGER])
        body = self.client.get(f'/customers/{self.customer.pk}/edit/?is_modal=1').content.decode('utf-8')
        self.assertIn('name="national_id"', body)

    def test_sales_is_limited(self):
        self.client.force_login(self.users[ROLE_SALES])
        self.assertFalse(has_permission(self.users[ROLE_SALES], 'customers.profile_full'))
        body = self.client.get(f'/customers/{self.customer.pk}/edit/?is_modal=1').content.decode('utf-8')
        self.assertNotIn('name="national_id"', body)

    def test_other_roles_limited_in_detail_page(self):
        for role in (ROLE_SALES, ROLE_SUPPORT, ROLE_OPERATOR,
                     ROLE_ACCOUNTANT, ROLE_ADS_MANAGER):
            with self.subTest(role=role):
                self.client.force_login(self.users[role])
                body = self.client.get(f'/customers/{self.customer.pk}/').content.decode('utf-8')
                self.assertNotIn('اطلاعات تماس', body)
