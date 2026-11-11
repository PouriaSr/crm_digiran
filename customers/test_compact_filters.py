import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import HttpResponseRedirect
from django.test import RequestFactory, TestCase
from django.urls import get_script_prefix, resolve, reverse, set_script_prefix
from django.utils import timezone

from crm.feedback import FeedbackContextMiddleware
from customers.models import Customer, FollowUp


class CompactFilterAndFeedbackTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin=User.objects.create_superuser('compact-admin')
        cls.now=timezone.now()
        cls.cards=[]
        for index in range(3):
            card=Customer.objects.create(name='مرتب سازی '+str(index),mobile=f'0912999000{index}',assigned_to=cls.admin)
            Customer.objects.filter(pk=card.pk).update(created_at=cls.now-timedelta(days=3-index))
            cls.cards.append(card)
        FollowUp.objects.create(customer=cls.cards[0],due_date=timezone.localdate()+timedelta(days=1))

    def setUp(self):
        self.client.force_login(self.admin)

    def test_only_information_filters_remain(self):
        response=self.client.get(reverse('customers:hub'),{'tab':'info'})
        self.assertEqual(list(response.context['customers']),list(reversed(self.cards)))
        for name in ('source','person_status','date_from','date_to','contact_expert'):
            self.assertContains(response,'name="'+name+'"')
        for name in ('display_mode','date_field','sort','priority'):
            self.assertNotIn('name="'+name+'"',response.content.decode().split('id="crm-task-queue-filters"')[0])

    def test_obsolete_modes_do_not_change_information_order_or_date_basis(self):
        for mode in ('oldest','followup','invalid'):
            response=self.client.get(reverse('customers:hub'),{'display_mode':mode,'sort':'priority','date_field':'followup'})
            self.assertEqual(list(response.context['customers']),list(reversed(self.cards)))
            self.assertEqual(response.context['table_filters']['date_field'],'created')

    def test_date_range_always_uses_registration_date(self):
        import jdatetime
        when=timezone.localdate()+timedelta(days=1)
        day=jdatetime.date.fromgregorian(date=when).strftime('%Y/%m/%d')
        for old_mode in ('followup','recent'):
            response=self.client.get(reverse('customers:hub'),{'display_mode':old_mode,'date_from':day,'date_to':day})
            self.assertFalse(list(response.context['customers']))

    def feedback_request(self,path,data):
        request=RequestFactory().post(path,data)
        request.session={}
        request._messages=FallbackStorage(request)
        request.resolver_match=resolve(path)
        return request

    def test_redirect_message_targets_reception_without_copying_form_values(self):
        request=self.feedback_request(reverse('customers:interview_save',args=[99]),{'password':'never-copy-this','notes':'private description'})
        def view(req):
            messages.success(req,'اطلاعات ثبت شد.')
            return HttpResponseRedirect(reverse('customers:hub')+'?tab=hiring&r=42')
        FeedbackContextMiddleware(view)(request)
        message=request._messages._queued_messages[0]
        context=json.loads(message.extra_tags)
        self.assertEqual(context['record'],'reception:42')
        self.assertNotIn('never-copy-this',message.extra_tags)
        self.assertNotIn('private description',message.extra_tags)
        self.assertEqual(message.level_tag,'success')

    def test_explicit_field_feedback_is_preserved(self):
        request=self.feedback_request(reverse('customers:interview_save',args=[99]),{})
        def view(req):
            messages.error(req,'کد ملی معتبر نیست.',extra_tags=json.dumps({'field':'id_national_id'}))
            return HttpResponseRedirect(reverse('customers:hub'))
        FeedbackContextMiddleware(view)(request)
        self.assertEqual(json.loads(request._messages._queued_messages[0].extra_tags),{'field':'id_national_id'})

    def test_script_prefix_and_created_record_feedback(self):
        request=self.feedback_request(reverse('products:create'),{})
        before=get_script_prefix()
        try:
            set_script_prefix('/test/')
            def view(req):
                messages.success(req,'کالا ثبت شد.')
                return HttpResponseRedirect('/test/products/123/')
            FeedbackContextMiddleware(view)(request)
            self.assertEqual(json.loads(request._messages._queued_messages[0].extra_tags)['record'],'product:123')
        finally:
            set_script_prefix(before)
