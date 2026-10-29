"""تست ماندگار: وضعیت دوگانه و تبعیت سیستم."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from customers.forms import CustomerForm
from customers.models import Customer, Reception


class TwoStateStatusTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('status_admin', password='t123456')
        cls.customer = Customer.objects.create(name='مشتری وضعیت', mobile='09121270001',
                                               stage='lead', assigned_to=cls.user,
                                               created_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)

    def _edit(self, stage):
        return self.client.post(
            f'/customers/{self.customer.pk}/edit/?is_modal=1',
            {'name': self.customer.name, 'mobile': self.customer.mobile,
             'national_id': '', 'birth_date': '', 'stage': stage, 'source': 'direct',
             'ad_source': '', 'assigned_to': self.user.pk, 'address': '',
             'notes': 'تست', 'email': ''},
            HTTP_HX_REQUEST='true',
        )

    # ── فرم ──
    def test_form_has_only_two_stage_choices(self):
        f = CustomerForm(instance=self.customer)
        self.assertIn('stage', f.fields)
        self.assertNotIn('status', f.fields)
        self.assertEqual([c[0] for c in f.fields['stage'].choices], ['potential', 'lead'])
        self.assertEqual(f.fields['stage'].label, 'وضعیت')

    # ── بالقوه ──
    def test_set_potential(self):
        r = self._edit('potential')
        self.customer.refresh_from_db()
        self.assertEqual(r.status_code, 204)
        self.assertEqual(self.customer.stage, 'potential')
        self.assertTrue(self.customer.needs_followup)

    def test_potential_requires_case_completion_for_registration(self):
        self._edit('potential')
        self.customer.refresh_from_db()
        rec = Reception.objects.create(customer=self.customer, person_type='customer',
                                       has_visit='yes', wait_choice='30')
        rec.refresh_from_db()
        self.assertTrue(rec.answers_complete, 'پاسخ‌ها کامل نیست')
        self.assertEqual(rec.customer.stage, 'potential')
        self.assertFalse(rec.can_submit_info)
        rec.case_completed_at = timezone.now()
        rec.save(update_fields=['case_completed_at'])
        self.assertTrue(rec.can_submit_info)

    def test_potential_shows_badge(self):
        self._edit('potential')
        body = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')
        self.assertIn('>بالقوه</span>', body)

    # ── فاقد شرایط ──
    def test_set_not_potential(self):
        Customer.objects.filter(pk=self.customer.pk).update(stage='potential',
                                                            needs_followup=True)
        r = self._edit('lead')
        self.customer.refresh_from_db()
        self.assertEqual(r.status_code, 204)
        self.assertEqual(self.customer.stage, 'lead')
        self.assertFalse(self.customer.needs_followup)

    def test_lead_without_case_is_not_ready_for_registration(self):
        self._edit('lead')
        rec = Reception.objects.create(customer=self.customer, person_type='customer',
                                       has_visit='yes', wait_choice='30')
        self.assertFalse(rec.can_submit_info)
