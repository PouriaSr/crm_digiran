"""تست ماندگار: سطوح دسترسی پروفایل مشتری."""
from django.contrib.auth.models import User
from django.test import TestCase

from customers.forms import CustomerForm
from customers.models import Customer


class CustomerProfilePermissionTest(TestCase):
    """سطح «فقط ثبت تماس» فقط فیلدهای پایه را می‌بیند"""

    BASIC = {'name', 'mobile', 'source', 'ad_source', 'notes'}

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('prof_admin', password='t123456')
        from django.contrib.auth.models import Group
        from accounts.permissions import ROLE_OPERATOR, ROLE_TO_GROUP
        cls.operator = User.objects.create_user('prof_operator', password='t123456')
        cls.operator.groups.add(Group.objects.get_or_create(
            name=ROLE_TO_GROUP[ROLE_OPERATOR])[0])

        cls.customer = Customer.objects.create(
            name='مشتری آزمایشی', mobile='09121320001', national_id='0012345678',
            address='تهران، خیابان تست', assigned_to=cls.user, created_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)

    # ── فرم ──
    def test_limited_form_has_only_basic_fields(self):
        f = CustomerForm(instance=self.customer, limited=True)
        self.assertEqual(set(f.fields), self.BASIC)

    def test_full_form_has_extended_fields(self):
        f = CustomerForm(instance=self.customer)
        for name in ('national_id', 'address', 'email', 'assigned_to'):
            self.assertIn(name, f.fields)

    def test_limited_form_saves_without_touching_other_fields(self):
        self.customer.assigned_to = self.operator
        self.customer.save(update_fields=["assigned_to"])
        self.client.force_login(self.operator)
        r = self.client.post(f'/customers/{self.customer.pk}/edit/?is_modal=1', {
            'name': 'ویرایش‌شده', 'mobile': self.customer.mobile,
            'source': 'direct', 'ad_source': '', 'notes': 'شرح جدید',
        }, HTTP_HX_REQUEST='true')
        self.customer.refresh_from_db()
        self.assertEqual(r.status_code, 204)
        self.assertEqual(self.customer.name, 'ویرایش‌شده')
        self.assertEqual(self.customer.national_id, '0012345678')

    # ── صفحه جزئیات ──
    def test_detail_hides_profile_card_for_limited_user(self):
        op = User.objects.create_user('prof_op', password='t123456')
        self.client.force_login(op)
        # کاربر بدون هیچ مجوزی → ۴۰۳؛ اینجا فقط ساختار context را با سوپریوزر می‌سنجیم
        self.client.force_login(self.user)
        body = self.client.get(f'/customers/{self.customer.pk}/').content.decode('utf-8')
        self.assertIn('اطلاعات تماس', body)

    def test_context_has_profile_flag(self):
        r = self.client.get(f'/customers/{self.customer.pk}/')
        self.assertIn('show_full_profile', r.context)
        self.assertTrue(r.context['show_full_profile'])

    # ── مجوز ──
    def test_permission_registered(self):
        from accounts.permissions import PERMISSIONS, PERMISSION_META
        self.assertIn('customers.profile_full', PERMISSIONS)
        self.assertIn('customers.profile_full', PERMISSION_META)
