"""
تست‌های dashboard — BI permission
"""
from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.urls import reverse

from accounts.forms import ensure_groups, ROLE_GROUP_MAP


class BIPermissionTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        ensure_groups()

        cls.admin = User.objects.create_superuser('bi_admin', password='t123456')

        cls.sm = User.objects.create_user('bi_sm', password='t123456')
        cls.sm.groups.add(Group.objects.get(name=ROLE_GROUP_MAP['sales_manager']))

        cls.sales = User.objects.create_user('bi_sales', password='t123456')
        cls.sales.groups.add(Group.objects.get(name=ROLE_GROUP_MAP['sales']))

        cls.accountant = User.objects.create_user('bi_acc', password='t123456')
        cls.accountant.groups.add(Group.objects.get(name=ROLE_GROUP_MAP['accountant']))

    def test_admin_can_access_bi(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse('dashboard:bi'))
        self.assertEqual(r.status_code, 200)

    def test_sales_manager_can_access_bi(self):
        self.client.force_login(self.sm)
        r = self.client.get(reverse('dashboard:bi'))
        self.assertEqual(r.status_code, 200)

    def test_sales_cannot_access_bi(self):
        self.client.force_login(self.sales)
        r = self.client.get(reverse('dashboard:bi'))
        self.assertEqual(r.status_code, 403)

    def test_accountant_cannot_access_bi(self):
        self.client.force_login(self.accountant)
        r = self.client.get(reverse('dashboard:bi'))
        self.assertEqual(r.status_code, 403)

    def test_admin_can_export_bi_excel(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse('dashboard:bi_export'))
        self.assertEqual(r.status_code, 200)
        self.assertIn(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            r['Content-Type'],
        )

    def test_sales_cannot_export_bi_excel(self):
        self.client.force_login(self.sales)
        r = self.client.get(reverse('dashboard:bi_export'))
        self.assertEqual(r.status_code, 403)