"""تست ماندگار: تقویم شمسی روی همه‌ی فیلدهای تاریخ + حالت فقط‌انتخاب."""
import re

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer


class DateCalendarTest(TestCase):
    """همه فیلدهای تاریخ باید data-jdp داشته باشند و تایپ دستی ممکن نباشد"""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('cal_admin', password='t123456')
        cls.customer = Customer.objects.create(name='مشتری تقویم', mobile='09121380001',
                                               assigned_to=cls.user, created_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)

    def _tags(self, body, names):
        out = {}
        for name in names:
            m = re.search(rf'<input[^>]*name="{name}"[^>]*>', body, re.S)
            out[name] = m.group(0) if m else ''
        return out

    def test_hub_date_fields_have_calendar(self):
        body = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')
        tags = self._tags(body, ['follow_up_date', 'next_follow_up_date'])
        for name, tag in tags.items():
            with self.subTest(field=name):
                self.assertIn('data-jdp', tag)

    def test_global_autoreadonly(self):
        body = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')
        self.assertIn('autoReadOnlyInput: true', body)

    def test_picker_watcher_on_htmx(self):
        body = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')
        self.assertIn("addEventListener('htmx:afterSwap'", body)

    def test_quick_modal_calls_startwatch(self):
        body = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')
        self.assertIn('jalaliDatepicker.startWatch();', body)

    def test_birth_date_has_calendar(self):
        body = self.client.get(f'/customers/{self.customer.pk}/edit/?is_modal=1').content.decode('utf-8')
        tag = self._tags(body, ['birth_date'])['birth_date']
        self.assertIn('data-jdp', tag)

    def test_dashboard_dates_have_calendar(self):
        body = self.client.get('/').content.decode('utf-8')
        for name, tag in self._tags(body, ['from_date', 'to_date']).items():
            with self.subTest(field=name):
                self.assertIn('data-jdp', tag)
