"""تست ماندگار: دسترسی تب واحد استخدام هم‌سطح تب پرونده."""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from accounts.permissions import ROLE_SALES_MANAGER, ROLE_SUPPORT, ROLE_TO_GROUP
from customers.models import Customer, Reception


class RecruitmentTabPermissionTest(TestCase):
    """واحد استخدام همان مجوز تب پرونده را می‌خواهد (customers.case)"""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('recp_admin', password='t123456')
        cls.cand = Customer.objects.create(name='کاندید', mobile='09121300001',
                                           stage='potential', assigned_to=cls.admin,
                                           created_by=cls.admin)
        Reception.objects.create(customer=cls.cand, person_type='interviewer',
                                 wait_choice='30')

        cls.mgr = User.objects.create_user('recp_mgr', password='t123456')
        cls.mgr.groups.add(Group.objects.get_or_create(
            name=ROLE_TO_GROUP[ROLE_SALES_MANAGER])[0])

        cls.sup = User.objects.create_user('recp_sup', password='t123456')
        cls.sup.groups.add(Group.objects.get_or_create(
            name=ROLE_TO_GROUP[ROLE_SUPPORT])[0])

    def setUp(self):
        self.hub = reverse('customers:hub')

    def test_admin_sees_tab(self):
        self.client.force_login(self.admin)
        body = self.client.get(f'{self.hub}?tab=info').content.decode('utf-8')
        self.assertIn("tab = 'recruitment'", body)

    def test_manager_sees_tab_like_case(self):
        self.client.force_login(self.mgr)
        body = self.client.get(f'{self.hub}?tab=info').content.decode('utf-8')
        self.assertEqual("tab = 'recruitment'" in body, "tab = 'case'" in body)
        self.assertIn("tab = 'recruitment'", body)

    def test_support_does_not_see_tab(self):
        self.client.force_login(self.sup)
        body = self.client.get(f'{self.hub}?tab=info').content.decode('utf-8')
        self.assertNotIn("tab = 'recruitment'", body)
        self.assertNotIn("tab = 'case'", body)

    def test_support_gets_no_recruiter_data(self):
        self.client.force_login(self.sup)
        r = self.client.get(f'{self.hub}?tab=recruitment')
        self.assertEqual(list(r.context['recruiter_rows']), [])

    def test_admin_gets_recruiter_data(self):
        self.client.force_login(self.admin)
        r = self.client.get(f'{self.hub}?tab=recruitment')
        self.assertIn(self.cand.pk, [x.customer_id for x in r.context['recruiter_rows']])
