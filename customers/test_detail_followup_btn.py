"""تست ماندگار: دکمه «ثبت پیگیری» در صفحه‌ی مشتری."""
import jdatetime
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.permissions import ROLE_SUPPORT, ROLE_TO_GROUP
from customers.models import Customer, FollowUp


class DetailFollowUpButtonTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('dfu_admin', password='t123456')
        cls.with_fu = Customer.objects.create(name='با پیگیری', mobile='09121430001',
                                              stage='potential', needs_followup=True,
                                              assigned_to=cls.user, created_by=cls.user)
        cls.no_fu = Customer.objects.create(name='بدون پیگیری', mobile='09121430002',
                                            stage='lead', assigned_to=cls.user,
                                            created_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)

    def _page(self, customer):
        return self.client.get(f'/customers/{customer.pk}/').content.decode('utf-8')

    # ── وضعیت دکمه ──
    def test_enabled_when_needs_followup(self):
        body = self._page(self.with_fu)
        self.assertIn(f"openQuickCall('followup', {self.with_fu.pk}", body)

    def test_disabled_when_no_followup(self):
        body = self._page(self.no_fu)
        self.assertNotIn(f"openQuickCall('followup', {self.no_fu.pk}", body)
        self.assertIn('ثبت نشده است', body)

    def test_button_in_header_and_bottom(self):
        body = self._page(self.with_fu)
        self.assertGreaterEqual(body.count(f"openQuickCall('followup', {self.with_fu.pk}"), 2)

    def test_opens_same_green_modal(self):
        body = self._page(self.with_fu)
        self.assertIn('id="qc-backdrop"', body)

    # ── عملکرد ──
    def test_followup_call_closes_followup(self):
        fu = FollowUp.objects.create(customer=self.with_fu,
                                     due_date=timezone.localdate())
        r = self.client.post(reverse('customers:quick_call', args=[self.with_fu.pk]), {
            'kind': 'followup', 'notes': 'پیگیری انجام شد',
            'follow_up_time': '10:30', 'follow_up_date': jdatetime.date.fromgregorian(date=timezone.localdate()).strftime('%Y/%m/%d'),
            'next': f'/customers/{self.with_fu.pk}/',
        })
        fu.refresh_from_db()
        self.with_fu.refresh_from_db()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers['Location'], f'/customers/{self.with_fu.pk}/')
        self.assertTrue(fu.is_done)
        self.assertFalse(self.with_fu.needs_followup)

    # ── دسترسی ──
    def test_support_role_sees_button(self):
        sup = User.objects.create_user('dfu_support', password='t123456')
        sup.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP[ROLE_SUPPORT])[0])
        self.client.force_login(sup)
        body = self._page(self.with_fu)
        self.assertIn('ثبت پیگیری', body)
