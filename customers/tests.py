"""
تست‌های customers — Duplicate Detection (۷.۵ ارتقاءیافته)

رفتار جدید:
- موبایل تکراری → ValidationError (بلاک سخت) → form invalid
- کد ملی تکراری → ValidationError (بلاک سخت) → form invalid
- نام/ایمیل مشابه → duplicate_warnings (soft) → form valid
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from .models import Customer
from .forms import CustomerForm


# ═══════════════════════════════════════════════════════════
# تست فرم — تشخیص exact (بلاک) و similar (هشدار)
# ═══════════════════════════════════════════════════════════
class CustomerFormDuplicateTest(TestCase):

    def setUp(self):
        self.existing = Customer.objects.create(
            name='مشتری موجود',
            mobile='09120000001',
            national_id='1234567890',
        )

    # ─── موبایل یکتا ───
    def test_unique_mobile_is_valid(self):
        form = CustomerForm(data={
            'name': 'مشتری جدید',
            'mobile': '09129999999',
            'status': 'lead',
            'source': 'direct',
            'notes': 'تست',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.duplicate_warnings, [])

    # ─── موبایل تکراری → BLOCK ───
    def test_duplicate_mobile_blocks_save(self):
        form = CustomerForm(data={
            'name': 'مشتری جدید',
            'mobile': '09120000001',
            'status': 'lead',
            'source': 'direct',
            'notes': 'تست',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('mobile', form.errors)
        self.assertIn('مشتری موجود', str(form.errors['mobile']))

    # ─── نرمال‌سازی موبایل — همه → BLOCK ───
    def test_mobile_with_spaces_blocks_duplicate(self):
        form = CustomerForm(data={
            'name': 'م',
            'mobile': ' 0912 000 0001 ',
            'status': 'lead',
            'source': 'direct',
            'notes': 'تست',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('mobile', form.errors)

    def test_mobile_with_spaces_normalizes_before_check(self):
        """نرمال‌سازی موبایل با فاصله — چک می‌کنیم که duplicate تشخیص داده بشه"""
        # اول چک کنیم فرم با موبایل فضادار، بدون در نظر گرفتن duplicate، نرمال می‌شه
        form = CustomerForm(data={
            'name': 'م',
            'mobile': ' 0912 000 0002 ',   # متفاوت از existing
            'status': 'lead',
            'source': 'direct',
            'notes': 'تست',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data.get('mobile'), '09120000002')

    def test_mobile_with_persian_digits_blocks_duplicate(self):
        form = CustomerForm(data={
            'name': 'م',
            'mobile': '۰۹۱۲۰۰۰۰۰۰۱',
            'status': 'lead',
            'source': 'direct',
            'notes': 'تست',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('mobile', form.errors)

    def test_mobile_with_persian_digits_normalizes_before_check(self):
        """نرمال‌سازی ارقام فارسی"""
        form = CustomerForm(data={
            'name': 'م',
            'mobile': '۰۹۱۲۰۰۰۰۰۰۲',   # متفاوت
            'status': 'lead',
            'source': 'direct',
            'notes': 'تست',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data.get('mobile'), '09120000002')

    def test_mobile_with_dashes_blocks_duplicate(self):
        form = CustomerForm(data={
            'name': 'م',
            'mobile': '0912-000-0001',
            'status': 'lead',
            'source': 'direct',
            'notes': 'تست',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('mobile', form.errors)

    # ─── کد ملی یکتا ───
    def test_unique_national_id_is_valid(self):
        form = CustomerForm(data={
            'name': 'م',
            'mobile': '09129999999',
            'national_id': '9999999999',
            'status': 'lead',
            'source': 'direct',
            'notes': 'تست',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.duplicate_warnings, [])

    # ─── کد ملی تکراری → BLOCK ───
    def test_duplicate_national_id_blocks_save(self):
        form = CustomerForm(data={
            'name': 'م',
            'mobile': '09129999999',
            'national_id': '1234567890',
            'status': 'lead',
            'source': 'direct',
            'notes': 'تست',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('national_id', form.errors)
        self.assertIn('مشتری موجود', str(form.errors['national_id']))

    # ─── کد ملی خالی → مجاز ───
    def test_empty_national_id_is_valid(self):
        form = CustomerForm(data={
            'name': 'م',
            'mobile': '09129999999',
            'national_id': '',
            'status': 'lead',
            'source': 'direct',
            'notes': 'تست',
        })
        self.assertTrue(form.is_valid(), form.errors)

    # ─── هر دو تکراری → BLOCK روی هر دو ───
    def test_both_duplicates_block_both_fields(self):
        form = CustomerForm(data={
            'name': 'م',
            'mobile': '09120000001',
            'national_id': '1234567890',
            'status': 'lead',
            'source': 'direct',
            'notes': 'تست',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('mobile', form.errors)
        self.assertIn('national_id', form.errors)

    # ─── ویرایش خود مشتری → مجاز ───
    def test_edit_self_no_block(self):
        form = CustomerForm(
            data={
                'name': 'مشتری موجود ویرایش',
                'mobile': '09120000001',
                'national_id': '1234567890',
                'status': 'active',
                'source': 'direct',
                'notes': 'تست',
            },
            instance=self.existing,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.duplicate_warnings, [])

    # ─── ویرایش → موبایل مشتری دیگه → BLOCK ───
    def test_edit_against_other_customer_blocks(self):
        other = Customer.objects.create(
            name='مشتری دیگر',
            mobile='09125555555',
        )
        form = CustomerForm(
            data={
                'name': 'مشتری دیگر ویرایش',
                'mobile': '09120000001',  # موبایل مشتری اول
                'status': 'lead',
                'source': 'direct',
                'notes': 'تست',
            },
            instance=other,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('mobile', form.errors)

    # ═══ مشابهت نام → هشدار (بدون بلاک) ═══
    def test_similar_name_shows_warning_not_block(self):
        """نام مشابه (فقط نویز فاصله) → warning، نه block"""
        form = CustomerForm(data={
            'name': 'مشتری  موجود',   # دو فاصله
            'mobile': '09129999999',
            'status': 'lead',
            'source': 'direct',
            'notes': 'تست',
        })
        self.assertTrue(form.is_valid(), form.errors)
        # باید حداقل یه warning برای name داشته باشه
        name_warnings = [w for w in form.duplicate_warnings if w['field'] == 'name']
        self.assertGreaterEqual(len(name_warnings), 1)
        self.assertEqual(name_warnings[0]['match'].pk, self.existing.pk)


# ═══════════════════════════════════════════════════════════
# تست view — رفتار بلاک و هشدار
# ═══════════════════════════════════════════════════════════
class CustomerDuplicateViewWarningTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser('admin', password='t123456')
        self.client.force_login(self.user)
        self.existing = Customer.objects.create(
            name='مشتری موجود',
            mobile='09120000001',
            assigned_to=self.user,
            created_by=self.user,
        )

    def _messages(self, response):
        return [str(m) for m in response.context['messages']]

    def _post_data(self, **overrides):
        data = {
            'name': 'مشتری جدید',
            'mobile': '09129999999',
            'status': 'lead',
            'source': 'direct',
            'assigned_to': self.user.pk,
            'notes': 'تست',
        }
        data.update(overrides)
        return data

    # ─── CREATE با موبایل تکراری → BLOCK ───
    def test_create_with_duplicate_mobile_is_blocked(self):
        """ثبت با موبایل تکراری → مشتری ذخیره نمی‌شه"""
        response = self.client.post(
            reverse('customers:create'),
            data=self._post_data(mobile='09120000001'),
        )
        # فرم invalid → 200 (همون صفحه با errors)
        self.assertEqual(response.status_code, 200)
        # مشتری جدید ساخته نشده
        self.assertFalse(Customer.objects.filter(name='مشتری جدید').exists())
        # خطا در فرم
        self.assertIn('mobile', response.context['form'].errors)

    # ─── CREATE با موبایل یکتا → موفق ───
    def test_create_with_unique_mobile_succeeds(self):
        response = self.client.post(
            reverse('customers:create'),
            data=self._post_data(mobile='09129999999'),
            follow=True,
        )
        self.assertTrue(Customer.objects.filter(name='مشتری جدید').exists())
        msgs = self._messages(response)
        # هیچ warning تکراری نباید باشه
        self.assertFalse(
            any('هشدار' in m and 'تکراری' in m for m in msgs),
            f'هشدار ناخواسته: {msgs}',
        )

    # ─── EDIT با موبایل مشتری دیگه → BLOCK ───
    def test_edit_with_duplicate_mobile_is_blocked(self):
        other = Customer.objects.create(
            name='دیگری',
            mobile='09125555555',
            assigned_to=self.user,
            created_by=self.user,
        )
        response = self.client.post(
            reverse('customers:edit', args=[other.pk]),
            data=self._post_data(name='دیگری ویرایش', mobile='09120000001'),
        )
        self.assertEqual(response.status_code, 200)
        # مطمئن شو mobile «other» تغییر نکرده
        other.refresh_from_db()
        self.assertEqual(other.mobile, '09125555555')

    # ─── EDIT خود مشتری → موفق ───
    def test_edit_self_no_block(self):
        response = self.client.post(
            reverse('customers:edit', args=[self.existing.pk]),
            data=self._post_data(
                name='مشتری موجود ویرایش',
                mobile='09120000001',
                status='active',
            ),
            follow=True,
        )
        self.existing.refresh_from_db()
        self.assertEqual(self.existing.name, 'مشتری موجود ویرایش')

    # ─── CREATE با نام مشابه → warning (ولی ذخیره می‌شه) ───
    def test_create_with_similar_name_shows_warning(self):
        """نام مشابه (فقط نویز فاصله) → ذخیره می‌شه + هشدار"""
        response = self.client.post(
            reverse('customers:create'),
            data=self._post_data(
                name='مشتری  موجود',   # دو فاصله
                mobile='09129999999',
            ),
            follow=True,
        )
        # مشتری جدید ساخته شده
        self.assertTrue(Customer.objects.filter(mobile='09129999999').exists())
        # پیام هشدار
        msgs = self._messages(response)
        self.assertTrue(
            any('هشدار' in m and 'مشتری موجود' in m for m in msgs),
            f'هشدار یافت نشد. پیام‌ها: {msgs}',
        )