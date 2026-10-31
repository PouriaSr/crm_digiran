"""تست ماندگار: وضعیت و هدف تماس در فرم سبز ثبت تماس جدید."""
from ads.models import AdSource
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from accounts.permissions import ROLE_OPERATOR, ROLE_SALES_MANAGER, ROLE_TO_GROUP
from calls.models import Call
from customers.models import Customer


class CallStatusPurposeTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('csp_admin', password='t123456')
        cls.customer = Customer.objects.create(name='مشتری فیلدها', mobile='09121450001',
                                               assigned_to=cls.admin, created_by=cls.admin)
        cls.operator = User.objects.create_user('csp_op', password='t123456')
        cls.operator.groups.add(Group.objects.get_or_create(
            name=ROLE_TO_GROUP[ROLE_OPERATOR])[0])
        cls.manager = User.objects.create_user('csp_mgr', password='t123456')
        cls.manager.groups.add(Group.objects.get_or_create(
            name=ROLE_TO_GROUP[ROLE_SALES_MANAGER])[0])

    def setUp(self):
        self.client.force_login(self.admin)

    def _page(self, user=None):
        if user:
            self.client.force_login(user)
        return self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')

    # ── فیلدها ──
    def test_status_field_with_four_options(self):
        body = self._page()
        self.assertIn('name="status" id="qc-status"', body)
        for value in ('answered', 'missed', 'busy', 'no_answer'):
            self.assertIn(f'value="{value}"', body)

    def test_purpose_field_options(self):
        body = self._page()
        self.assertIn('name="purpose" id="qc-purpose"', body)
        for value in ('sale', 'support', 'complaint'):
            self.assertIn(f'value="{value}"', body)

    # ── دسترسی گزینه «اطلاعات» ──
    def test_info_option_visible_with_case_permission(self):
        body = self._page(self.manager)
        self.assertIn('<option value="info">', body)

    def test_info_option_hidden_without_case_permission(self):
        body = self._page(self.operator)
        self.assertNotIn('<option value="info">', body)

    # ── ذخیره ──
    def test_saves_selected_values(self):
        self.client.post(reverse('customers:quick_call', args=[self.customer.pk]), {'source': AdSource.objects.get_or_create(phone_number='09129999888', defaults={'label':'تست'})[0].pk,
            'kind': 'new', 'notes': 'پشتیبانی', 'status': 'busy', 'purpose': 'support',
        })
        call = Call.objects.filter(customer=self.customer).order_by('-id').first()
        self.assertEqual(call.status, 'busy')
        self.assertEqual(call.purpose, 'support')

    def test_invalid_values_fall_back(self):
        self.client.post(reverse('customers:quick_call', args=[self.customer.pk]), {'source': AdSource.objects.get_or_create(phone_number='09129999888', defaults={'label':'تست'})[0].pk,
            'kind': 'new', 'notes': 'نامعتبر', 'status': 'x', 'purpose': 'y',
        })
        call = Call.objects.filter(customer=self.customer).order_by('-id').first()
        self.assertEqual(call.status, 'answered')
        self.assertEqual(call.purpose, 'sale')

    def test_operator_cannot_use_info_purpose(self):
        self.client.force_login(self.operator)
        self.client.post(reverse('customers:quick_call', args=[self.customer.pk]), {'source': AdSource.objects.get_or_create(phone_number='09129999888', defaults={'label':'تست'})[0].pk,
            'kind': 'new', 'notes': 'تلاش', 'purpose': 'info',
        })
        call = Call.objects.filter(customer=self.customer).order_by('-id').first()
        self.assertEqual(call.purpose, 'sale')

    def test_manager_can_use_info_purpose(self):
        self.client.force_login(self.manager)
        self.client.post(reverse('customers:quick_call', args=[self.customer.pk]), {'source': AdSource.objects.get_or_create(phone_number='09129999888', defaults={'label':'تست'})[0].pk,
            'kind': 'new', 'notes': 'اطلاعات', 'purpose': 'info',
        })
        call = Call.objects.filter(customer=self.customer).order_by('-id').first()
        self.assertEqual(call.purpose, 'info')
