"""تست ماندگار: اعتبارسنجی کد ملی/موبایل + هم‌خوانی وضعیت پیگیری."""
from ads.models import AdSource
from datetime import timedelta

import jdatetime
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from calls.models import Call
from customers.forms import CustomerForm
from customers.models import Customer, FollowUp


def jdate(d):
    return jdatetime.date.fromgregorian(date=d).strftime('%Y/%m/%d')


class NationalIdValidationTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('nid_admin', password='t123456')

    def setUp(self):
        self.client.force_login(self.user)

    def _form(self, national_id, mobile='09121234567'):
        return CustomerForm(data={
            'name': 'تست', 'mobile': mobile, 'national_id': national_id,
            'birth_date': '', 'stage': 'lead', 'source': 'direct', 'ad_source': '',
            'assigned_to': self.user.pk, 'address': '', 'notes': 'تست', 'email': '',
        })

    def test_invalid_short_code_rejected(self):
        f = self._form('222')
        self.assertFalse(f.is_valid())
        self.assertIn('national_id', f.errors)

    def test_invalid_checksum_rejected(self):
        f = self._form('1234567890')
        self.assertFalse(f.is_valid())
        self.assertIn('national_id', f.errors)

    def test_valid_code_accepted(self):
        f = self._form('0022962840')
        self.assertTrue(f.is_valid(), f.errors)

    def test_blank_code_allowed(self):
        f = self._form('')
        self.assertTrue(f.is_valid(), f.errors)

    def test_repeated_digits_rejected(self):
        f = self._form('1111111111')
        self.assertFalse(f.is_valid())

    def test_edit_blocked_for_invalid_stored_code(self):
        c = Customer.objects.create(name='کد خراب', mobile='09121230009',
                                    national_id='222', assigned_to=self.user,
                                    created_by=self.user)
        r = self.client.post(f'/customers/{c.pk}/edit/?is_modal=1', {
            'name': 'کد خراب', 'mobile': c.mobile, 'national_id': '222',
            'birth_date': '', 'stage': 'lead', 'source': 'direct', 'ad_source': '',
            'assigned_to': self.user.pk, 'address': '', 'notes': 'تست', 'email': '',
        }, HTTP_HX_REQUEST='true')
        c.refresh_from_db()
        self.assertEqual(r.status_code, 200)  # فرم با خطا برمی‌گردد، ذخیره نمی‌شود
        self.assertEqual(c.national_id, '222')


class MobileValidationTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('mob_admin', password='t123456')

    def _form(self, mobile):
        return CustomerForm(data={
            'name': 'تست موبایل', 'mobile': mobile, 'national_id': '',
            'birth_date': '', 'stage': 'lead', 'source': 'direct', 'ad_source': '',
            'assigned_to': self.user.pk, 'address': '', 'notes': 'تست', 'email': '',
        })

    def test_short_mobile_rejected(self):
        f = self._form('0912123')
        self.assertFalse(f.is_valid())
        self.assertIn('mobile', f.errors)

    def test_wrong_prefix_rejected(self):
        f = self._form('02112345678')
        self.assertFalse(f.is_valid())
        self.assertIn('mobile', f.errors)

    def test_valid_mobile_accepted(self):
        f = self._form('09121234567')
        self.assertTrue(f.is_valid(), f.errors)


class FollowUpStatusConsistencyTest(TestCase):
    """پیگیری‌ها باید در لیست و صفحه‌ی تماس یکسان دیده شوند"""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('fuc_admin', password='t123456')

    def setUp(self):
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(
            name='مشتری پیگیری', mobile='09121390001', stage='potential',
            needs_followup=True, assigned_to=self.user, created_by=self.user)

    def test_followup_call_records_done_even_without_open(self):
        """اگر پیگیری بازی نبود (داده قدیمی)، تماس پیگیری باز هم رکورد می‌سازد"""
        r = self.client.post(reverse('customers:quick_call', args=[self.customer.pk]), {'source': AdSource.objects.get_or_create(phone_number='09129999888', defaults={'label':'تست'})[0].pk,
            'kind': 'followup', 'notes': 'نتیجه ثبت شد',
            'follow_up_time': '10:30', 'follow_up_date': jdate(timezone.localdate()),
        })
        self.assertEqual(r.status_code, 302)
        fu = FollowUp.objects.filter(customer=self.customer).first()
        self.assertIsNotNone(fu)
        self.assertTrue(fu.is_done)

        body = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')
        self.assertIn('✓ انجام شد', body)

    def test_list_shows_open_badge(self):
        FollowUp.objects.create(customer=self.customer,
                                due_date=timezone.localdate() + timedelta(days=2))
        body = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')
        self.assertIn('● باز', body)

    def test_closing_followup_then_list_shows_done(self):
        FollowUp.objects.create(customer=self.customer,
                                due_date=timezone.localdate())
        self.client.post(reverse('customers:quick_call', args=[self.customer.pk]), {'source': AdSource.objects.get_or_create(phone_number='09129999888', defaults={'label':'تست'})[0].pk,
            'kind': 'followup', 'notes': 'بسته شد',
            'follow_up_time': '10:30', 'follow_up_date': jdate(timezone.localdate()),
        })
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.needs_followup)
        body = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')
        self.assertIn('✓ انجام شد', body)
