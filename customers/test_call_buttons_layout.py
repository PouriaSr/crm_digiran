"""تست ماندگار: چیدمان دکمه‌های ثبت تماس/پیگیری در کارت «آخرین تماس‌ها»."""
import re

from django.contrib.auth.models import User
from django.test import TestCase

from customers.models import Customer


class CallButtonsLayoutTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('cbl_admin', password='t123456')
        cls.with_fu = Customer.objects.create(name='با پیگیری', mobile='09121440001',
                                              stage='potential', needs_followup=True,
                                              assigned_to=cls.user, created_by=cls.user)
        cls.no_fu = Customer.objects.create(name='بدون پیگیری', mobile='09121440002',
                                            stage='lead', assigned_to=cls.user,
                                            created_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)

    def _block(self, customer):
        body = self.client.get(f'/customers/{customer.pk}/').content.decode('utf-8')
        start = body.find('آخرین تماس‌ها')
        section = body[start:start + 4000]
        w = section.find('flex items-center gap-1.5 shrink-0')
        if w == -1:
            return ''
        end = section.find('\n        </div>', w)
        return section[w:end] if end != -1 else section[w:]

    # ── کنار هم ──
    def test_both_buttons_in_one_group(self):
        block = self._block(self.with_fu)
        self.assertIn("openQuickCall('new'", block)
        self.assertIn("openQuickCall('followup'", block)

    def test_order_new_before_followup(self):
        block = self._block(self.with_fu)
        self.assertLess(block.find('ثبت تماس جدید'), block.find('ثبت پیگیری'))

    # ── استایل ──
    def test_pill_styles(self):
        block = self._block(self.with_fu)
        self.assertIn('bg-sky-50 text-sky-700', block)
        self.assertIn('bg-emerald-50 text-emerald-700', block)
        self.assertIn('rounded-lg', block)
        self.assertIn('h-8', block)

    def test_no_plain_link_style(self):
        block = self._block(self.with_fu)
        self.assertNotIn('hover:underline', block)

    # ── حالت غیرفعال ──
    def test_disabled_state_for_customer_without_followup(self):
        block = self._block(self.no_fu)
        self.assertNotIn("openQuickCall('followup'", block)
        self.assertIn('cursor-not-allowed', block)
        self.assertIn('ثبت نشده است', block)
