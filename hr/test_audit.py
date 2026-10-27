"""تست‌های بازرسی HR: مرزهای دسترسی مرخصی‌ها."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from hr.models import Employee, LeaveRequest


class LeaveAccessScopeTest(TestCase):
    """کاربر بدون مجوز بررسی، فقط مرخصی خودش را می‌بیند"""

    @classmethod
    def setUpTestData(cls):
        cls.u1 = User.objects.create_user('hr_emp1', password='t123456')
        cls.u2 = User.objects.create_user('hr_emp2', password='t123456')
        cls.e1 = Employee.objects.create(user=cls.u1, first_name='الف', last_name='یک',
                                         national_id='0010000101', mobile='09120001001',
                                         position='sales', contract_type='full_time')
        cls.e2 = Employee.objects.create(user=cls.u2, first_name='ب', last_name='دو',
                                         national_id='0010000202', mobile='09120001002',
                                         position='sales', contract_type='full_time')
        cls.l1 = LeaveRequest.objects.create(employee=cls.e1, leave_type='annual',
                                             start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
                                             reason='مرخصی من')
        cls.l2 = LeaveRequest.objects.create(employee=cls.e2, leave_type='annual',
                                             start_date=date(2026, 2, 1), end_date=date(2026, 2, 2),
                                             reason='مرخصی دیگری')

    def test_employee_sees_only_own_leaves(self):
        self.client.force_login(self.u1)
        r = self.client.get(reverse('hr:leave_list'))
        self.assertEqual(r.status_code, 200)
        items = list(r.context['page_obj'].object_list)
        self.assertEqual(len(items), 1, 'کارمند باید فقط مرخصی خودش را ببیند')
        self.assertEqual(items[0].pk, self.l1.pk)

    def test_manager_sees_all_leaves(self):
        admin = User.objects.create_superuser('hr_mgr', password='t123456')
        self.client.force_login(admin)
        r = self.client.get(reverse('hr:leave_list'))
        items = list(r.context['page_obj'].object_list)
        self.assertEqual(len(items), 2, 'مدیر باید همه‌ی مرخصی‌ها را ببیند')

    def test_user_without_profile_cannot_create_leave(self):
        outsider = User.objects.create_user('hr_out', password='t123456')
        self.client.force_login(outsider)
        r = self.client.post(reverse('hr:leave_create'), {
            'employee': self.e2.pk, 'leave_type': 'annual',
            'start_date': '1405/05/01', 'end_date': '1405/05/02', 'reason': 'تقلب',
        })
        self.assertEqual(r.status_code, 302)
        self.assertFalse(LeaveRequest.objects.filter(reason='تقلب').exists())
