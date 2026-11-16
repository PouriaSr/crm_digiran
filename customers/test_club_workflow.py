from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from hr.models import Task
from products.models import Category, Product

from .club_models import ClubAccount, ClubPayment, LoanEvaluation, LoanProgram
from .club_service import covered_purchase_amount, evaluate_case, purchase_budget, purchase_difference
from .models import Customer, CustomerCase, Reception


class ClubWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('club_admin')
        cls.category, _ = Category.objects.get_or_create(slug='mobile', defaults={'name': 'گوشی موبایل'})
        cls.phone = Product.objects.create(category=cls.category, name='گوشی تست', code='PHONE-1',
                                           price=55_000_000, cost_price=40_000_000, stock=3)

    def setUp(self):
        self.client.force_login(self.admin)
        self.customer = Customer.objects.create(name='مشتری باشگاه', mobile='09121112233', assigned_to=self.admin)
        self.rec = Reception.objects.create(
            customer=self.customer, person_type='customer', referred_at=timezone.now(), referred_to=self.admin,
            registration_completed_at=timezone.now(), case_completed_at=timezone.now(), case_result='bought',
        )
        self.case = CustomerCase.objects.create(
            customer=self.customer, condition='cash', job='private', credit_rank='A1',
            visit_result='bought', contract_number='DG-TEST-0001', created_by=self.admin,
        )

    def test_rules_exclude_active_provider_and_require_wiki_guarantor(self):
        programs, products, rejected = evaluate_case(self.case, 100_000_000, 0)
        self.assertTrue(any(item.provider == 'azki' for item in programs))
        self.assertFalse(any(item.provider == 'wiki_pay' for item in programs))
        self.assertIn(self.phone, products)
        self.case.active_loans = ['azki']
        self.case.guarantor_name = 'ضامن نمونه'
        self.case.guarantor_credit_rank = 'A1'
        self.case.save()
        programs, _, _ = evaluate_case(self.case, 100_000_000, 0)
        self.assertFalse(any(item.provider == 'azki' for item in programs))
        self.assertTrue(any(item.provider == 'wiki_pay' for item in programs))

        # A B-ranked applicant may use an A/B guarantor, but not a C guarantor.
        self.case.active_loans = []
        self.case.credit_rank = 'B1'
        self.case.guarantor_credit_rank = 'C1'
        self.case.save()
        programs, _, _ = evaluate_case(self.case, 100_000_000, 0)
        self.assertFalse(any(item.provider == 'wiki_pay' for item in programs))
        self.case.guarantor_credit_rank = 'B3'
        self.case.save(update_fields=['guarantor_credit_rank'])
        programs, _, _ = evaluate_case(self.case, 100_000_000, 0)
        self.assertTrue(any(item.provider == 'wiki_pay' for item in programs))

    def test_evaluate_select_contract_and_payment_schedule(self):
        response = self.client.post(reverse('customers:club_evaluate', args=[self.rec.pk]), {
            'requested_credit': 100_000_000, 'proposed_down_payment': 0,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['programs'])
        self.assertEqual(data['products'][0]['id'], self.phone.pk)
        evaluation = LoanEvaluation.objects.get(pk=data['evaluation'])
        program = LoanProgram.objects.get(pk=data['programs'][0]['id'])
        response = self.client.post(reverse('customers:club_select', args=[self.rec.pk]), {
            'evaluation': evaluation.pk, 'program': program.pk, 'product': self.phone.pk,
            'delivery_type': 'instant', 'club_fee': 500_000,
        })
        self.assertEqual(response.status_code, 200)
        account = ClubAccount.objects.get(customer=self.customer)
        self.assertEqual(account.contract_number, self.case.contract_number)
        self.assertEqual(account.panel_label, 'پنل B2B')
        self.assertEqual(account.payments.filter(payment_type='installment').count(), program.term_months)
        self.assertTrue(account.payments.filter(payment_type='club_fee', amount=500_000).exists())
        task = Task.objects.get(source_key=f'club:{self.rec.pk}')
        self.assertEqual(task.status, 'done')

    def test_evaluation_explains_why_no_offer_is_available(self):
        self.case.credit_rank = ''
        self.case.save(update_fields=['credit_rank'])
        response = self.client.post(reverse('customers:club_evaluate', args=[self.rec.pk]), {
            'requested_credit': 100_000_000, 'proposed_down_payment': 0,
        })
        self.assertEqual(response.status_code, 422)
        self.assertIn('رتبه اعتباری مشتری در پرونده ثبت نشده', response.json()['message'])
        self.assertFalse(LoanEvaluation.objects.filter(reception=self.rec).exists())

    def test_evaluation_explains_when_no_phone_matches_budget(self):
        self.phone.stock = 0
        self.phone.save(update_fields=['stock'])
        response = self.client.post(reverse('customers:club_evaluate', args=[self.rec.pk]), {
            'requested_credit': 100_000_000, 'proposed_down_payment': 0,
        })
        self.assertEqual(response.status_code, 422)
        self.assertIn('گوشی فعال و موجود', response.json()['message'])

    def test_down_payment_is_free_amount_and_unlocks_affordable_programs(self):
        azki = LoanProgram.objects.get(provider='azki', term_months=12)
        self.assertEqual(purchase_budget(azki, 0), 62_000_000)
        self.assertEqual(purchase_budget(azki, 10_000_000), 72_000_000)
        self.assertEqual(purchase_budget(azki, 50_000_000), 85_000_000)

        response = self.client.post(reverse('customers:club_evaluate', args=[self.rec.pk]), {
            'requested_credit': 100_000_000, 'proposed_down_payment': 15_000_000,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        providers = {item['provider'] for item in data['programs']}
        self.assertIn('جی‌اس‌ام', providers)
        self.assertIn('ستاره یک', providers)
        gsm = LoanProgram.objects.get(provider='gsm', term_months=12)
        response = self.client.post(reverse('customers:club_select', args=[self.rec.pk]), {
            'evaluation': data['evaluation'], 'program': gsm.pk, 'product': self.phone.pk,
            'delivery_type': 'delayed', 'club_fee': 0,
        })
        self.assertEqual(response.status_code, 200)
        account = ClubAccount.objects.get(customer=self.customer)
        self.assertTrue(account.payments.filter(
            payment_type='down_payment', amount=15_000_000,
        ).exists())

    def test_phone_difference_is_offered_and_added_to_receiptable_payments(self):
        phone = Product.objects.create(
            category=self.category, name='گوشی با مابه‌التفاوت', code='PHONE-DIFF',
            price=90_000_000, cost_price=70_000_000, stock=1,
        )
        response = self.client.post(reverse('customers:club_evaluate', args=[self.rec.pk]), {
            'requested_credit': 100_000_000, 'proposed_down_payment': 0,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn(phone.pk, {item['id'] for item in data['products']})
        azki_data = next(item for item in data['programs'] if item['provider'] == 'ازکی')
        azki = LoanProgram.objects.get(pk=azki_data['id'])
        self.assertEqual(azki_data['contribution'], covered_purchase_amount(azki, 0))
        self.assertEqual(purchase_difference(azki, 0, phone.price), 28_000_000)
        response = self.client.post(reverse('customers:club_select', args=[self.rec.pk]), {
            'evaluation': data['evaluation'], 'program': azki.pk, 'product': phone.pk,
            'delivery_type': 'instant', 'club_fee': 0,
        })
        self.assertEqual(response.status_code, 200)
        account = ClubAccount.objects.get(customer=self.customer)
        difference = account.payments.get(payment_type='purchase_difference')
        self.assertEqual(difference.amount, 28_000_000)
        self.assertEqual(difference.status, 'scheduled')

    def test_private_receipt_and_card_ownership_are_enforced(self):
        evaluation = LoanEvaluation.objects.create(
            reception=self.rec, case=self.case, requested_credit=100_000_000, proposed_down_payment=0,
            contract_number=self.case.contract_number, created_by=self.admin,
        )
        program = LoanProgram.objects.filter(provider='azki').first()
        account = ClubAccount.objects.create(
            customer=self.customer, reception=self.rec, evaluation=evaluation,
            contract_number=self.case.contract_number, loan_program=program, product=self.phone,
            delivery_type='delayed', panel_url='https://example.com/b2c', customer_credit_rank='A1',
            selected_by=self.admin,
        )
        payment = ClubPayment.objects.create(account=account, payment_type='other', amount=1000)
        self.assertEqual(self.client.get(reverse('customers:club_receipt', args=[payment.pk])).status_code, 404)
        other = User.objects.create_user('club_other')
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse('customers:club_payment', args=[account.pk]), {}).status_code, 403)

    def test_club_tab_is_conditional_and_contains_program_settings_for_admin(self):
        response = self.client.get(reverse('customers:hub'), {'tab': 'club', 'r': self.rec.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'باشگاه مشتریان')
        self.assertContains(response, 'تنظیمات طرح‌های وام')
        self.assertEqual(response.context['club_record'], self.rec)

    def test_bought_case_creates_contract_pending_task_and_opens_club(self):
        customer = Customer.objects.create(
            name='خریدار جدید', mobile='09129998877', assigned_to=self.admin,
        )
        rec = Reception.objects.create(
            customer=customer, person_type='customer', referred_at=timezone.now(),
            referred_to=self.admin, registration_completed_at=timezone.now(),
        )
        response = self.client.post(reverse('customers:case_save'), {
            'reception': rec.pk, 'condition': 'cash', 'job': 'private',
            'credit_rank': 'A1', 'quantity': 1, 'visit_result': 'bought',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('tab=club', response.url)
        case = CustomerCase.objects.get(customer=customer)
        self.assertTrue(case.contract_number.startswith('DG-'))
        rec.refresh_from_db()
        self.assertEqual(rec.case_result, 'bought')
        task = Task.objects.get(source_key=f'club:{rec.pk}')
        self.assertEqual(task.status, 'pending')
