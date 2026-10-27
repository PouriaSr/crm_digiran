from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from customers.models import Customer
from calls.models import Call
from ads.models import AdSource

class CustomerFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin', 'a@a.com', 'password')
        self.client.force_login(self.user)
        self.ad_source = AdSource.objects.create(phone_number='09120000000', label='تست')

    def test_create_customer_form_logic(self):
        # تست ثبت مشتری با منبع جذب 'تبلیغات' و منبع آگهی
        response = self.client.post(reverse('customers:create'), {
            'name': 'تست مشتری',
            'mobile': '09121111111',
            'status': 'lead',
            'source': 'ads',
            'ad_source': self.ad_source.id,
            'notes': 'یادداشت تستی',
        })
        self.assertEqual(response.status_code, 302) # باید موفق باشد و ریدایرکت شود
        
        customer = Customer.objects.get(mobile='09121111111')
        self.assertEqual(customer.source, 'ads')
        self.assertEqual(customer.ad_source, self.ad_source)
        self.assertEqual(customer.assigned_to, self.user) # کارمند مسئول باید خودکار پر شود

    def test_create_customer_without_notes_fails(self):
        # تست اجباری بودن یادداشت
        response = self.client.post(reverse('customers:create'), {
            'name': 'تست بدون یادداشت',
            'mobile': '09122222222',
            'status': 'lead',
            'source': 'website',
            'notes': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Customer.objects.filter(mobile='09122222222').exists())

class HubCallFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin', 'a@a.com', 'password')
        self.client.force_login(self.user)
        # ⭐ AdSource ایجاد می‌شود (لازم برای source field)
        self.ad_source = AdSource.objects.create(
            phone_number='09120000000', label='تست',
        )

    def test_hub_call_outgoing(self):
        # تست ثبت تماس خروجی
        response = self.client.post(reverse('customers:hub_submit_call'), {
            'mobile': '09123333333',
            'name': 'مشتری خروجی',
            'call_type': 'followup',
            'source': str(self.ad_source.pk),  # ⭐ source صحیح
            'customer_type': 'none',
            'status': 'active',
            'notes': 'تماس خروجی تست',
            'follow_up_time': '10:30', 'follow_up_date': '',
            'installments_count': '',
            'cheques_count': '',
        })
        call = Call.objects.filter(call_number='09123333333').first()
        self.assertIsNotNone(call, "Call باید ساخته بشه")
        self.assertEqual(call.call_type, 'outgoing')
        self.assertEqual(call.status, 'answered')

    def test_hub_call_incoming_missed(self):
        # تست ثبت تماس از دست رفته
        response = self.client.post(reverse('customers:hub_submit_call'), {
            'mobile': '09124444444',
            'name': 'مشتری از دست رفته',
            'call_type': 'missed',
            'source': str(self.ad_source.pk),  # ⭐ source صحیح
            'customer_type': 'none',
            'status': 'lead',
            'follow_up_time': '10:30', 'follow_up_date': '1405/01/01',
            'notes': 'تماس از دست رفته تست',
            'installments_count': '',
            'cheques_count': '',
        })
        call = Call.objects.filter(call_number='09124444444').first()
        self.assertIsNotNone(call, "Call باید ساخته بشه")
        self.assertEqual(call.call_type, 'incoming')
        self.assertEqual(call.status, 'missed')
