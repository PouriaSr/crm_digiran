"""New-call registration: validation, independent choices, case prefill and SMS intent."""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from calls.models import Call
from customers.forms import HubCallForm, CustomerForm
from customers.models import Customer, CustomerCase, FollowUp, Reception
from customers.sms import send_address_sms


class CallRegistrationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('registration_admin', password='t123456')

    def setUp(self):
        self.client.force_login(self.admin)
        self.url = reverse('customers:hub_submit_call')
        self.data = {
            'mobile': '09123456789', 'name': 'مشتری جدید', 'call_type': 'incoming',
            'notes': 'توضیحات تماس', 'purpose': 'sale', 'call_status': 'answered',
            'customer_analysis': 'lead', 'requested_condition': 'cheque',
        }

    def submit(self, **updates):
        return self.client.post(self.url, {**self.data, **updates})

    def test_phone_rejects_missing_short_long_and_non_digits_without_writes(self):
        for mobile in ('', '0912345678', '091234567890', '0912345678a', '۰۹۱۲۳۴۵۶۷۸a'):
            with self.subTest(mobile=mobile):
                self.submit(mobile=mobile, send_address='on')
                self.assertFalse(Call.objects.exists())
                self.assertFalse(Customer.objects.exists())
                self.assertFalse(CustomerCase.objects.exists())

    def test_phone_accepts_and_normalizes_persian_and_arabic_digits(self):
        for mobile in ('۰۹۱۲۳۴۵۶۷۸۹', '٠٩١٢٣٤٥٦٧٨٩'):
            with self.subTest(mobile=mobile):
                form = HubCallForm({**self.data, 'mobile': mobile})
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data['mobile'], '09123456789')

    def test_name_is_required_even_for_existing_customer(self):
        Customer.objects.create(name='نام قبلی', mobile=self.data['mobile'])
        for name in ('', '  '):
            self.submit(name=name)
            self.assertFalse(Call.objects.exists())
        self.assertEqual(Customer.objects.get().name, 'نام قبلی')

    def test_names_with_numbers_are_rejected_without_writes(self):
        for name in ('مریم 123', 'علی۱۲۳', 'مینا١٢٣', 'Test１２', 'Name²'):
            with self.subTest(name=name):
                self.submit(name=name)
                self.assertFalse(Call.objects.exists())
                self.assertFalse(Customer.objects.exists())

    def test_persian_and_latin_names_are_accepted(self):
        for name in ('مریم احمدی', 'علی\u200cرضا حسینی', "Anne-Marie O'Connor"):
            with self.subTest(name=name):
                form = HubCallForm({**self.data, 'name': name})
                self.assertTrue(form.is_valid(), form.errors)

    def test_purpose_and_status_are_saved_independently_of_contact_type(self):
        self.submit(call_type='missed', purpose='support', call_status='busy')
        call = Call.objects.get()
        self.assertEqual((call.contact_type, call.purpose, call.status), ('missed', 'support', 'busy'))

    def test_invalid_choices_do_not_write(self):
        for field in ('purpose', 'call_status', 'customer_analysis', 'requested_condition'):
            with self.subTest(field=field):
                self.submit(**{field: 'invalid'})
                self.assertFalse(Call.objects.exists())
                self.assertFalse(Customer.objects.exists())

    def test_analysis_potential_does_not_require_followup_or_send_sms(self):
        with patch('customers.hub_views.send_address_sms') as sms:
            self.submit(customer_analysis='potential')
        customer = Customer.objects.get()
        self.assertEqual(customer.stage, 'potential')
        self.assertFalse(customer.needs_followup)
        self.assertFalse(FollowUp.objects.exists())
        self.assertEqual(Call.objects.get().declared_customer_status, 'lead')
        sms.assert_not_called()

    def test_followup_does_not_override_explicit_lead_analysis_or_trigger_sms(self):
        with patch('customers.hub_views.send_address_sms') as sms:
            self.submit(needs_followup='on', follow_up_date='1405/09/15')
        self.assertEqual(Customer.objects.get().stage, 'lead')
        self.assertTrue(Customer.objects.get().needs_followup)
        self.assertEqual(FollowUp.objects.count(), 1)
        self.assertEqual(Call.objects.get().declared_customer_status, 'none')
        sms.assert_not_called()

    def test_address_can_be_requested_without_followup(self):
        with patch('customers.hub_views.send_address_sms', return_value=False) as sms:
            response = self.submit(send_address='on')
        sms.assert_called_once_with(Customer.objects.get())
        self.assertTrue(Call.objects.get().send_address)
        self.assertFalse(FollowUp.objects.exists())
        messages = [str(m) for m in response.wsgi_request._messages]
        self.assertTrue(any('پیامک واقعی ارسال نشده' in message for message in messages))

    def test_address_with_followup_only_calls_sms_hook_once(self):
        with patch('customers.hub_views.send_address_sms', return_value=False) as sms:
            self.submit(send_address='on', needs_followup='on', follow_up_date='1405/09/15')
        sms.assert_called_once()
        self.assertEqual(FollowUp.objects.count(), 1)

    def test_test_sms_is_explicitly_not_sent_and_does_not_log_phone(self):
        customer = Customer.objects.create(name='مشتری', mobile=self.data['mobile'])
        with self.assertLogs('crm.sms', level='INFO') as logs:
            self.assertFalse(send_address_sms(customer))
        self.assertIn('TEST ONLY; NOT SENT', logs.output[0])
        self.assertNotIn(customer.mobile, logs.output[0])

    def test_invalid_or_missing_followup_date_causes_no_partial_writes(self):
        for date in ('', '1405/99/01', 'not-a-date'):
            with self.subTest(date=date), patch('customers.hub_views.send_address_sms') as sms:
                self.submit(needs_followup='on', follow_up_date=date, send_address='on')
                self.assertFalse(Customer.objects.exists())
                self.assertFalse(Call.objects.exists())
                sms.assert_not_called()

    def test_existing_open_followup_is_not_cleared_by_new_normal_call(self):
        customer = Customer.objects.create(name='مشتری', mobile=self.data['mobile'], needs_followup=True)
        FollowUp.objects.create(customer=customer, due_date='2026-12-01')
        self.submit()
        customer.refresh_from_db()
        self.assertTrue(customer.needs_followup)
        self.assertTrue(customer.followups.filter(is_done=False).exists())

    def test_case_is_prefilled_later_without_creating_an_incomplete_case(self):
        self.submit(customer_analysis='potential', requested_condition='retired')
        customer = Customer.objects.get()
        self.assertEqual(Call.objects.get().requested_condition, 'retired')
        self.assertFalse(CustomerCase.objects.exists())
        Reception.objects.create(customer=customer, person_type='customer', info_submitted=True)
        response = self.client.get(reverse('customers:hub'), {'tab': 'case', 'c': customer.pk})
        form = response.context['case_form']
        self.assertEqual(form['condition'].value(), 'retired')
        self.assertEqual(form['job'].value(), 'retired')
        self.assertFalse(form['credit_rank'].value())
        self.assertFalse(CustomerCase.objects.exists())

    def test_existing_case_information_is_preserved(self):
        customer = Customer.objects.create(name='مشتری', mobile=self.data['mobile'], stage='potential')
        case = CustomerCase.objects.create(customer=customer, condition='cash', job='private')
        self.submit(customer_analysis='potential', requested_condition='retired')
        response = self.client.get(reverse('customers:hub'), {'tab': 'case', 'c': customer.pk})
        self.assertEqual(response.context['case_form']['condition'].value(), 'cash')
        self.assertEqual(response.context['case_form']['job'].value(), 'private')
        case.refresh_from_db()
        self.assertEqual((case.condition, case.job), ('cash', 'private'))

    def test_all_requested_conditions_are_available_in_call_and_case_forms(self):
        from customers.forms import CustomerCaseForm
        expected = {'cheque', 'retired', 'cash', 'credit', 'other'}
        self.assertEqual({v for v, label in HubCallForm().fields['requested_condition'].choices if v}, expected)
        self.assertEqual({v for v, label in CustomerCaseForm().fields['condition'].choices if v}, expected)

    def test_modal_contains_required_fields_and_separate_address_toggle(self):
        response = self.client.get(reverse('customers:hub'))
        for name in ('purpose', 'call_status', 'customer_analysis', 'requested_condition', 'send_address'):
            self.assertContains(response, f'name="{name}"')
        form = HubCallForm()
        self.assertTrue(form.fields['name'].required)
        self.assertTrue(form.fields['mobile'].required)

    def test_profile_stage_change_no_longer_automatically_sends_sms(self):
        customer = Customer.objects.create(name='مشتری', mobile=self.data['mobile'])
        form = CustomerForm({
            'name': customer.name, 'mobile': customer.mobile, 'stage': 'potential',
            'source': 'direct', 'notes': 'توضیح',
        }, instance=customer)
        self.assertTrue(form.is_valid(), form.errors)
        with patch('customers.sms.send_address_sms') as sms:
            form.save()
        sms.assert_not_called()

    def test_anonymous_registration_is_rejected(self):
        self.client.logout()
        self.submit()
        self.assertFalse(Call.objects.exists())
