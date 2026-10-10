"""
تست‌های customers — ۷.۵ چک تکراری موبایل و کد ملی
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from .models import Customer
from .forms import CustomerForm


# ═══════════════════════════════════════════════════════════
# تست فرم — تشخیص تکراری
# ═══════════════════════════════════════════════════════════
class CustomerFormDuplicateTest(TestCase):

    def setUp(self):
        self.existing = Customer.objects.create(
            name='مشتری موجود',
            mobile='09120000001',
            national_id='1234567890',
        )

    def test_no_warning_for_unique_mobile(self):
        form = CustomerForm(data={
            'name': 'مشتری جدید',
            'mobile': '09129999999',
            'status': 'lead',
            'source': 'direct',
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(form.duplicate_warnings, [])

    def test_warning_for_duplicate_mobile(self):
        form = CustomerForm(data={
            'name': 'مشتری جدید',
            'mobile': '09120000001',
            'status': 'lead',
            'source': 'direct',
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(len(form.duplicate_warnings), 1)
        self.assertEqual(form.duplicate_warnings[0]['field'], 'mobile')
        self.assertEqual(form.duplicate_warnings[0]['customer'].pk, self.existing.pk)

    def test_mobile_with_spaces_detects_duplicate(self):
        form = CustomerForm(data={
            'name': 'م',
            'mobile': ' 0912 000 0001 ',
            'status': 'lead',
            'source': 'direct',
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['mobile'], '09120000001')
        self.assertEqual(len(form.duplicate_warnings), 1)

    def test_mobile_with_persian_digits_detects_duplicate(self):
        form = CustomerForm(data={
            'name': 'م',
            'mobile': '۰۹۱۲۰۰۰۰۰۰۱',
            'status': 'lead',
            'source': 'direct',
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['mobile'], '09120000001')
        self.assertEqual(len(form.duplicate_warnings), 1)

    def test_mobile_with_dashes_detects_duplicate(self):
        form = CustomerForm(data={
            'name': 'م',
            'mobile': '0912-000-0001',
            'status': 'lead',
            'source': 'direct',
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(len(form.duplicate_warnings), 1)

    def test_no_warning_for_unique_national_id(self):
        form = CustomerForm(data={
            'name': 'م',
            'mobile': '09129999999',
            'national_id': '9999999999',
            'status': 'lead',
            'source': 'direct',
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(form.duplicate_warnings, [])

    def test_warning_for_duplicate_national_id(self):
        form = CustomerForm(data={
            'name': 'م',
            'mobile': '09129999999',
            'national_id': '1234567890',
            'status': 'lead',
            'source': 'direct',
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(len(form.duplicate_warnings), 1)
        self.assertEqual(form.duplicate_warnings[0]['field'], 'national_id')

    def test_no_warning_for_empty_national_id(self):
        form = CustomerForm(data={
            'name': 'م',
            'mobile': '09129999999',
            'national_id': '',
            'status': 'lead',
            'source': 'direct',
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(form.duplicate_warnings, [])

    def test_both_mobile_and_national_id_duplicate(self):
        form = CustomerForm(data={
            'name': 'م',
            'mobile': '09120000001',
            'national_id': '1234567890',
            'status': 'lead',
            'source': 'direct',
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(len(form.duplicate_warnings), 2)
        fields = {w['field'] for w in form.duplicate_warnings}
        self.assertEqual(fields, {'mobile', 'national_id'})

    def test_edit_self_no_warning(self):
        form = CustomerForm(
            data={
                'name': 'مشتری موجود ویرایش',
                'mobile': '09120000001',
                'national_id': '1234567890',
                'status': 'active',
                'source': 'direct',
            },
            instance=self.existing,
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.duplicate_warnings, [])

    def test_edit_against_other_customer_warning(self):
        other = Customer.objects.create(
            name='مشتری دیگر',
            mobile='09125555555',
        )
        form = CustomerForm(
            data={
                'name': 'مشتری دیگر ویرایش',
                'mobile': '09120000001',
                'status': 'lead',
                'source': 'direct',
            },
            instance=other,
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(len(form.duplicate_warnings), 1)
        self.assertEqual(form.duplicate_warnings[0]['field'], 'mobile')
        self.assertEqual(form.duplicate_warnings[0]['customer'].pk, self.existing.pk)


# ═══════════════════════════════════════════════════════════
# تست view — پیام هشدار
# ═══════════════════════════════════════════════════════════
class CustomerDuplicateViewWarningTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser('admin', password='t123456')
        self.client.force_login(self.user)
        # ⭐ assigned_to و created_by ست می‌شن تا template کرش نکنه
        self.existing = Customer.objects.create(
            name='مشتری موجود',
            mobile='09120000001',
            assigned_to=self.user,
            created_by=self.user,
        )

    def _messages(self, response):
        return [str(m) for m in response.context['messages']]

    def _post_data(self, **overrides):
        """دیتای پایه با assigned_to ست‌شده"""
        data = {
            'name': 'مشتری جدید',
            'mobile': '09129999999',
            'status': 'lead',
            'source': 'direct',
            'assigned_to': self.user.pk,
        }
        data.update(overrides)
        return data

    def test_create_with_duplicate_mobile_shows_warning(self):
        """ثبت با موبایل تکراری → مشتری ذخیره می‌شه + هشدار"""
        response = self.client.post(
            reverse('customers:create'),
            data=self._post_data(mobile='09120000001'),
            follow=True,
        )
        self.assertTrue(Customer.objects.filter(name='مشتری جدید').exists())
        msgs = self._messages(response)
        self.assertTrue(
            any('مشتری موجود' in m and 'هشدار' in m for m in msgs),
            f'پیام هشدار یافت نشد. پیام‌ها: {msgs}',
        )

    def test_create_with_unique_mobile_no_warning(self):
        """موبایل یکتا → بدون هشدار"""
        response = self.client.post(
            reverse('customers:create'),
            data=self._post_data(mobile='09129999999'),
            follow=True,
        )
        msgs = self._messages(response)
        self.assertFalse(
            any('هشدار' in m and 'تکراری' in m for m in msgs),
            f'هشدار ناخواسته: {msgs}',
        )

    def test_edit_with_duplicate_mobile_shows_warning(self):
        """ویرایش با موبایل تکراری → هشدار"""
        other = Customer.objects.create(
            name='دیگری',
            mobile='09125555555',
            assigned_to=self.user,
            created_by=self.user,
        )
        response = self.client.post(
            reverse('customers:edit', args=[other.pk]),
            data=self._post_data(name='دیگری ویرایش', mobile='09120000001'),
            follow=True,
        )
        msgs = self._messages(response)
        self.assertTrue(
            any('مشتری موجود' in m and 'هشدار' in m for m in msgs),
            f'پیام هشدار یافت نشد. پیام‌ها: {msgs}',
        )

    def test_edit_self_no_warning(self):
        """ویرایش خود مشتری → بدون هشدار"""
        response = self.client.post(
            reverse('customers:edit', args=[self.existing.pk]),
            data=self._post_data(
                name='مشتری موجود ویرایش',
                mobile='09120000001',
                status='active',
            ),
            follow=True,
        )
        msgs = self._messages(response)
        self.assertFalse(
            any('هشدار' in m and 'تکراری' in m for m in msgs),
            f'هشدار ناخواسته: {msgs}',
        )