from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from calls.models import Call
from .forms import HubCallForm
from .models import Customer, Reception, FollowUp, HiringApplication


class CandidateRegistrationTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_superuser('candidate_admin')
        self.client.force_login(self.user)
        self.url=reverse('customers:hub_submit_call')
        self.data={'name':'مریم احمدی','mobile':'۰۹۱۲۳۴۵۶۷۸۹','is_interviewer':'on'}

    def test_name_and_phone_are_sufficient_and_extras_ignored(self):
        data={**self.data,'source':'invalid','notes':'نباید ثبت شود','needs_followup':'on',
              'send_address':'on','follow_up_date':'bad','customer_analysis':'potential'}
        form=HubCallForm(data,user=self.user)
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(set(form.cleaned_data),{'name','mobile','is_interviewer'})
        response=self.client.post(self.url,data)
        self.assertEqual(response.status_code,302)
        person=Customer.objects.get()
        self.assertTrue(person.is_interviewer)
        self.assertEqual(person.mobile,'09123456789')
        self.assertFalse(person.notes)
        self.assertFalse(person.needs_followup)
        for model in (Call,FollowUp,Reception,HiringApplication):
            self.assertFalse(model.objects.exists())
        response=self.client.get(response.url)
        self.assertContains(response,'مصاحبه‌کننده')

    def test_existing_or_inactive_person_is_preserved(self):
        for inactive in (False,True):
            existing=Customer.all_objects.create(name='نام قبلی',mobile='09123456789',notes='شرح قبلی',is_deleted=inactive)
            self.client.post(self.url,self.data)
            self.assertEqual(Customer.all_objects.count(),1)
            existing.refresh_from_db()
            self.assertEqual(existing.name,'نام قبلی')
            self.assertEqual(existing.notes,'شرح قبلی')
            self.assertFalse(existing.is_interviewer)
            Customer.all_objects.filter(pk=existing.pk).delete()

    def test_ordinary_call_keeps_required_fields_and_candidate_validates_identity(self):
        ordinary=HubCallForm({'name':'مریم','mobile':'09123456789'},user=self.user)
        self.assertFalse(ordinary.is_valid())
        self.assertIn('notes',ordinary.errors)
        form=HubCallForm({**self.data,'mobile':'123'},user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('mobile',form.errors)
