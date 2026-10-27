"""تست ماندگار: ویرایش تماس‌های گذشته (عادی و پیگیری)."""
import jdatetime
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from calls.models import Call
from customers.models import Customer, FollowUp


def jdate(d):
    return jdatetime.date.fromgregorian(date=d).strftime('%Y/%m/%d')


class CallEditTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('ce_admin', password='t123456')
        cls.customer = Customer.objects.create(name='مشتری ویرایش', mobile='09121490001',
                                               assigned_to=cls.user, created_by=cls.user)
        cls.normal = Call.objects.create(
            customer=cls.customer, caller_name=cls.customer.name,
            call_number=cls.customer.mobile, call_type='incoming',
            contact_type='incoming', purpose='sale', status='answered',
            notes='شرح اول', called_by=cls.user)
        cls.follow = Call.objects.create(
            customer=cls.customer, caller_name=cls.customer.name,
            call_number=cls.customer.mobile, call_type='outgoing',
            contact_type='followup', purpose='followup', status='followup',
            notes='پیگیری اول', called_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)

    # ── UI ──
    def test_modal_in_hub_and_detail(self):
        hub = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')
        detail = self.client.get(f'/customers/{self.customer.pk}/').content.decode('utf-8')
        for body in (hub, detail):
            self.assertIn('id="ce-backdrop"', body)
            self.assertIn('onclick="openCallEdit(this)"', body)

    def test_rows_carry_call_data(self):
        hub = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')
        self.assertIn(f'data-call-id="{self.normal.pk}"', hub)
        self.assertIn(f'data-call-id="{self.follow.pk}"', hub)

    # ── ویرایش عادی ──
    def test_edit_normal_call(self):
        self.client.post(reverse('customers:hub_call_edit', args=[self.normal.pk]), {
            'notes': 'شرح جدید', 'status': 'busy', 'purpose': 'support',
            'call_date': jdate(timezone.localdate()),
        })
        self.normal.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(self.normal.notes, 'شرح جدید')
        self.assertEqual(self.normal.status, 'busy')
        self.assertEqual(self.normal.purpose, 'support')
        self.assertEqual(self.customer.notes, 'شرح جدید')

    def test_edit_requires_notes(self):
        self.client.post(reverse('customers:hub_call_edit', args=[self.normal.pk]), {
            'notes': '', 'status': 'busy',
        })
        self.normal.refresh_from_db()
        self.assertEqual(self.normal.notes, 'شرح اول')

    def test_invalid_status_ignored(self):
        self.client.post(reverse('customers:hub_call_edit', args=[self.normal.pk]), {
            'notes': 'تست', 'status': 'hack', 'purpose': 'hack',
        })
        self.normal.refresh_from_db()
        self.assertEqual(self.normal.status, 'answered')
        self.assertEqual(self.normal.purpose, 'sale')

    # ── ویرایش پیگیری ──
    def test_edit_followup_closes_open_followup(self):
        FollowUp.objects.create(customer=self.customer, due_date=timezone.localdate())
        self.client.post(reverse('customers:hub_call_edit', args=[self.follow.pk]), {
            'notes': 'نتیجه', 'follow_up_time': '10:30', 'follow_up_date': jdate(timezone.localdate()),
            'is_followed_up': '1',
        })
        self.follow.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertTrue(self.follow.is_followed_up)
        self.assertIsNotNone(self.follow.follow_up_date)
        self.assertEqual(FollowUp.objects.filter(customer=self.customer, is_done=False).count(), 0)
        self.assertFalse(self.customer.needs_followup)

    # ── دسترسی ──
    def test_permission_required(self):
        outsider = User.objects.create_user('ce_outsider', password='t123456')
        self.client.force_login(outsider)
        r = self.client.post(reverse('customers:hub_call_edit', args=[self.normal.pk]),
                             {'notes': 'x'})
        self.assertEqual(r.status_code, 403)
