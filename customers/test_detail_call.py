from ads.models import AdSource
"""تست ماندگار: دکمه ثبت تماس در صفحه‌ی مشتری همان مودال تب اطلاعات است."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer, FollowUp


class DetailCallButtonParityTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('dc_admin', password='t123456')
        cls.customer = Customer.objects.create(name='مریم تست', mobile='09121400001',
                                               assigned_to=cls.user, created_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)

    def _detail(self):
        return self.client.get(f'/customers/{self.customer.pk}/').content.decode('utf-8')

    # ── همان مودال ──
    def test_detail_includes_same_modal(self):
        body = self._detail()
        for token in ('id="call-modal-root"', 'name="needs_followup"',
                      'name="follow_up_date"', 'id="hub_followup_date"'):
            self.assertIn(token, body)

    def test_uses_reliable_open_path(self):
        body = self._detail()
        self.assertIn("if (typeof openNewCall === 'function') {", body)
        self.assertIn('lock: true', body)

    def test_passes_next_url(self):
        body = self._detail()
        self.assertIn('next: window.location.pathname', body)
        self.assertIn('id="hub_call_next"', body)

    # ── بازگشت ──
    def test_submit_returns_to_customer_page(self):
        r = self.client.post(reverse('customers:hub_submit_call'), {'purpose':'sale', 'call_status':'answered', 'customer_analysis':'lead', 'requested_condition':'cash',
            'mobile': '09121400002', 'name': 'مشتری از صفحه', 'call_type': 'incoming',
            'notes': 'ثبت از صفحه مشتری', 'source': AdSource.objects.get_or_create(phone_number='09129999888', defaults={'label':'تست'})[0].pk,
            'next': f'/customers/{self.customer.pk}/',
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers['Location'], f'/customers/{self.customer.pk}/')

    def test_external_next_is_blocked(self):
        r = self.client.post(reverse('customers:hub_submit_call'), {'purpose':'sale', 'call_status':'answered', 'customer_analysis':'lead', 'requested_condition':'cash',
            'mobile': '09121400003', 'name': 'تست امنیت', 'call_type': 'incoming',
            'notes': 'تست', 'source': AdSource.objects.get_or_create(phone_number='09129999888', defaults={'label':'تست'})[0].pk,
            'next': 'https://evil.example.com/',
        })
        self.assertEqual(r.headers['Location'], '/customers/hub/?tab=call')

    def test_no_next_goes_to_hub(self):
        r = self.client.post(reverse('customers:hub_submit_call'), {'purpose':'sale', 'call_status':'answered', 'customer_analysis':'lead', 'requested_condition':'cash',
            'mobile': '09121400005', 'name': 'بدون next', 'call_type': 'incoming',
            'notes': 'تست', 'source': AdSource.objects.get_or_create(phone_number='09129999888', defaults={'label':'تست'})[0].pk,
        })
        self.assertEqual(r.headers['Location'], '/customers/hub/?tab=call')

    # ── پیگیری از همان مسیر ──
    def test_followup_created_from_detail_path(self):
        mobile = '09121400004'
        self.client.post(reverse('customers:hub_submit_call'), {'purpose':'sale', 'call_status':'answered', 'customer_analysis':'lead', 'requested_condition':'cash', 'source':AdSource.objects.get_or_create(phone_number='09129999888', defaults={'label':'تست'})[0].pk,
            'mobile': mobile, 'name': 'با پیگیری', 'call_type': 'incoming',
            'notes': 'نیاز به پیگیری', 'needs_followup': 'on',
            'follow_up_time': '10:30', 'follow_up_date': '1405/08/20', 'next': f'/customers/{self.customer.pk}/',
        })
        c = Customer.objects.filter(mobile=mobile).first()
        self.assertIsNotNone(c)
        self.assertTrue(FollowUp.objects.filter(customer=c, is_done=False).exists())
