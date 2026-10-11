"""
تست‌های hr — Duplicate Detection Employee
"""
from django.test import TestCase
from django.contrib.auth.models import User

from .models import Employee
from .forms import EmployeeForm


class EmployeeDuplicateTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.existing = Employee.objects.create(
            first_name='علی',
            last_name='رضایی',
            mobile='09120000001',
            national_id='1234567890',
            position='sales',
        )

    def _form_data(self, **overrides):
        data = {
            'first_name': 'محمد',
            'last_name': 'احمدی',
            'mobile': '09129999999',
            'national_id': '9999999999',
            'email': '',
            'position': 'sales',
            'contract_type': 'full_time',
            'hire_date': '1404/01/15',
            'salary': 0,
            'is_active': True,
            'address': '',
            'notes': '',
        }
        data.update(overrides)
        return data

    def test_unique_employee_is_valid(self):
        form = EmployeeForm(data=self._form_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_duplicate_mobile_blocks(self):
        form = EmployeeForm(data=self._form_data(mobile='09120000001'))
        self.assertFalse(form.is_valid())
        self.assertIn('mobile', form.errors)

    def test_duplicate_national_id_blocks(self):
        form = EmployeeForm(data=self._form_data(national_id='1234567890'))
        self.assertFalse(form.is_valid())
        self.assertIn('national_id', form.errors)

    def test_mobile_normalization_persian_digits(self):
        """موبایل با ارقام فارسی → نرمال‌سازی"""
        form = EmployeeForm(data=self._form_data(mobile='۰۹۱۲۰۰۰۰۰۰۱'))
        self.assertFalse(form.is_valid())
        self.assertIn('mobile', form.errors)

    def test_edit_self_no_block(self):
        """ویرایش خود کارمند → block نکنه"""
        form = EmployeeForm(
            data=self._form_data(
                first_name='علی ویرایش',
                mobile='09120000001',
                national_id='1234567890',
            ),
            instance=self.existing,
        )
        self.assertTrue(form.is_valid(), form.errors)