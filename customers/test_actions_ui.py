"""تست ماندگار: طراحی دکمه‌های عملیات جدول مشتریان."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer


class ActionsUIRedesignTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('ui_admin', password='t123456')
        cls.with_fu = Customer.objects.create(name='با پیگیری', mobile='09121370001',
                                              stage='potential', needs_followup=True,
                                              assigned_to=cls.user, created_by=cls.user)
        cls.no_fu = Customer.objects.create(name='بدون پیگیری', mobile='09121370002',
                                            stage='lead', assigned_to=cls.user,
                                            created_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)
        self.body = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')

    # ── ساختار ──
    def test_uses_shared_button_classes(self):
        self.assertIn('hub-act hub-act-primary', self.body)
        self.assertIn('hub-act-sky', self.body)
        self.assertIn('hub-act-icon hub-act-violet', self.body)

    def test_single_line_layout(self):
        self.assertIn('flex-nowrap', self.body)
        self.assertIn('w-px h-5 bg-gray-200', self.body)

    def test_styles_loaded_once_in_page(self):
        self.assertIn('.hub-act-primary', self.body)

    def test_partial_has_no_style_block(self):
        partial = self.client.get(reverse('customers:hub') + '?tab=info',
                                  headers={'HX-Request': 'true'}).content.decode('utf-8')
        self.assertNotIn('<style>', partial)
        self.assertIn('hub-act hub-act-primary', partial)

    # ── برچسب و دسترس‌پذیری ──
    def test_labels_and_tooltips(self):
        for text in ('<span>پیگیری</span>', '<span>تماس جدید</span>',
                     'title="انتقال به کارمند دیگر"', 'title="ویرایش اطلاعات"',
                     'title="غیرفعال‌سازی"'):
            self.assertIn(text, self.body)

    def test_icon_buttons_have_aria_labels(self):
        for label in ('aria-label="انتقال"', 'aria-label="ویرایش"',
                      'aria-label="غیرفعال‌سازی"'):
            self.assertIn(label, self.body)

    # ── عملکردها ──
    def test_handlers_intact(self):
        self.assertIn(f"openQuickCall('followup', {self.with_fu.pk}", self.body)
        self.assertIn(f"openQuickCall('new', {self.with_fu.pk}", self.body)
        self.assertIn(f'openReassignModal({self.with_fu.pk}', self.body)
        self.assertIn(f'/customers/{self.with_fu.pk}/edit/?is_modal=1', self.body)
        self.assertIn(f'/customers/{self.with_fu.pk}/deactivate/', self.body)

    def test_followup_disabled_when_not_needed(self):
        self.assertIn('hub-act-primary-off', self.body)
        self.assertIn('ثبت نشده است', self.body)

    def test_table_scrolls_horizontally(self):
        self.assertIn('overflow-x-auto', self.body)
