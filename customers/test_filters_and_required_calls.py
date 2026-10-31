from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
import jdatetime
from ads.models import AdSource
from customers.models import Customer, FollowUp
from customers.forms import HubCallForm

class FilterAndCallRequirementsTest(TestCase):
    def setUp(self):
        self.user=User.objects.create_superuser('validation_admin')
        self.client.force_login(self.user)
        self.customer=Customer.objects.create(name='مشتری بدون پیگیری',mobile='09121234567')
        self.source=AdSource.objects.create(label='منبع تست',phone_number='09129999999')

    def test_default_date_range_filters_creation_even_without_followup(self):
        date=jdatetime.date.fromgregorian(date=timezone.localdate()).strftime('%Y/%m/%d')
        response=self.client.get(reverse('customers:hub'),{'date_from':date,'date_to':date})
        self.assertIn(self.customer,list(response.context['customers']))
        self.assertEqual(response.context['table_filters']['date_field'],'created')
        response=self.client.get(reverse('customers:hub'),{'date_field':'followup','date_from':date,'date_to':date})
        self.assertNotIn(self.customer,list(response.context['customers']))
        FollowUp.objects.create(customer=self.customer,due_date=timezone.localdate())
        response=self.client.get(reverse('customers:hub'),{'date_field':'followup','date_from':date,'date_to':date})
        self.assertIn(self.customer,list(response.context['customers']))

    def test_required_call_fields_cannot_be_omitted(self):
        data={'name':'مشتری تست','mobile':'09121234567','call_type':'incoming','purpose':'sale',
              'call_status':'answered','customer_analysis':'lead','requested_condition':'cash',
              'source':self.source.pk,'notes':'شرح تست'}
        self.assertTrue(HubCallForm(data).is_valid())
        for field in data:
            invalid=dict(data);invalid.pop(field)
            form=HubCallForm(invalid)
            self.assertFalse(form.is_valid(),field)
            self.assertIn(field,form.errors)
