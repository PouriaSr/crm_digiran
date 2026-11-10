from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
import jdatetime
from ads.models import AdSource
from customers.models import Customer
from accounts.models import UserPermissionOverride


class InformationFiltersTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_superuser('info_filter_admin')
        self.client.force_login(self.user)
        self.ad=AdSource.objects.create(label='منبع خاص',phone_number='09124449999')
        self.lead=Customer.objects.create(name='سرنخ فیلتر',mobile='09124441111',source='direct',assigned_to=self.user)
        self.potential=Customer.objects.create(name='بالقوه فیلتر',mobile='09124441112',stage='potential',source='ads',ad_source=self.ad,assigned_to=self.user)
        self.candidate=Customer.objects.create(name='کارجو فیلتر',mobile='09124441113',is_interviewer=True,assigned_to=self.user)

    def results(self,**params):
        response=self.client.get(reverse('customers:hub'),{'tab':'info',**params})
        self.assertEqual(response.status_code,200)
        return {item.pk for item in response.context['customers']}

    def test_status_source_owner_dates_combine_and_obsolete_filters_are_ignored(self):
        self.assertEqual(self.results(),{self.lead.pk,self.potential.pk,self.candidate.pk})
        self.assertEqual(self.results(person_status='interviewer'),{self.candidate.pk})
        self.assertEqual(self.results(person_status='lead',source='direct'),{self.lead.pk})
        date=jdatetime.date.fromgregorian(date=timezone.localdate()).strftime('%Y/%m/%d')
        self.assertEqual(self.results(person_status='potential',source='ad:'+str(self.ad.pk),contact_expert=self.user.pk,date_from=date,date_to=date),{self.potential.pk})
        self.assertEqual(self.results(priority='none',display_mode='followup'),self.results())
        self.assertEqual(self.results(date_from='نامعتبر'),set())

    def test_only_requested_filter_controls_are_rendered(self):
        response=self.client.get(reverse('customers:hub'),{'tab':'info','source':'ad:'+str(self.ad.pk)})
        form=response.content.decode().split('id="hub-filter-form"',1)[1].split('</form>',1)[0]
        for key in ('source','person_status','date_from','date_to','contact_expert'):
            self.assertIn('name="'+key+'"',form)
        for key in ('priority','display_mode','visit'):
            self.assertNotIn('name="'+key+'"',form)
        self.assertIn(f'value="ad:{self.ad.pk}" selected',form)
