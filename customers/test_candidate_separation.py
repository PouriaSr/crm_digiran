from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.core.paginator import Paginator
from django.template import Context, Template
from accounts.models import UserPermissionOverride
from .models import Customer, Reception


class CandidateSeparationTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_superuser('separate_admin')
        self.client.force_login(self.admin)
        self.person=Customer.objects.create(name='کارجوی مستقل',mobile='09121112233',is_interviewer=True,assigned_to=self.admin)

    def test_profile_is_recruitment_only_and_sales_actions_are_blocked(self):
        response=self.client.get(reverse('customers:detail',args=[self.person.pk]))
        self.assertEqual(response.status_code,200)
        self.assertTemplateUsed(response,'customers/candidate_detail.html')
        self.assertNotContains(response,'openQuickCall')
        self.assertNotContains(response,'id="call-modal-root"')
        self.assertEqual(self.client.post(reverse('customers:quick_call',args=[self.person.pk]),{'notes':'نباید ثبت شود'}).status_code,403)
        self.assertEqual(self.client.get(reverse('customers:edit',args=[self.person.pk])).status_code,403)
        self.assertEqual(self.client.post(reverse('customers:hub_submit_call'),{'name':self.person.name,'mobile':self.person.mobile,'is_interviewer':'false'}).status_code,403)

    def test_candidates_are_not_in_customer_list_but_have_their_own_list(self):
        response=self.client.get(reverse('customers:hub'),{'tab':'info'})
        self.assertNotIn(self.person,list(response.context['customers']))
        response=self.client.get(reverse('customers:candidate_list'))
        self.assertContains(response,self.person.name)

    def test_reception_uses_candidate_identity_even_if_wrong_type_is_posted(self):
        self.client.post(reverse('customers:reception_action'),{'action':'arrive','customer':self.person.pk,'person_type':'customer'})
        self.assertEqual(Reception.objects.get(customer=self.person).person_type,'interviewer')

    def test_advanced_denial_and_unowned_profiles_are_enforced(self):
        user=User.objects.create_user('candidate_scoped')
        for permission in ('customers.view','customers.candidate_view'):
            UserPermissionOverride.objects.create(user=user,permission_key=permission,granted=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('customers:detail',args=[self.person.pk])).status_code,403)
        self.assertNotContains(self.client.get(reverse('customers:candidate_list')),self.person.name)

    def test_numbered_pagination_preserves_filters_and_other_lists(self):
        request=RequestFactory().get('/customers/hub/?tab=hiring&q=test&ad_page=3&partial=1')
        page=Paginator(range(120),10).get_page(4)
        html=Template('{% load fa_numbers %}{% page_controls page "hiring_page" "hiring" %}').render(Context({'request':request,'page':page}))
        self.assertIn('aria-current="page"',html)
        self.assertIn('hiring_page=1',html)
        self.assertIn('hiring_page=5',html)
        self.assertIn('ad_page=3',html)
        self.assertNotIn('partial=1',html)
        self.assertIn('شماره صفحه مقصد',html)

    def test_legacy_alignment_preserves_history_and_releases_wrong_open_visit(self):
        from django.apps import apps
        from django.db import connection
        from importlib import import_module
        from calls.models import Call
        from hr.models import Task
        from .models import FollowUp
        from django.utils import timezone
        old=Customer.objects.create(name='سابقه قدیمی',mobile='09129990001',needs_followup=True,notes='حفظ یادداشت')
        interview=Reception.objects.create(customer=old,person_type='interviewer',workflow_version=1)
        wrong=Reception.objects.create(customer=old,person_type='customer',workflow_version=2)
        Call.objects.create(customer=old,caller_name=old.name,call_number=old.mobile,call_date=timezone.now(),notes='حفظ تماس')
        task=Task.objects.create(title='پیگیری قدیمی',source_type='customer_followup',source_key='legacy-test',source_customer=old)
        run=import_module('customers.migrations.0027_separate_candidates').align_candidates
        editor=type('Editor',(),{'connection':connection})()
        run(apps,editor);run(apps,editor)
        old.refresh_from_db();wrong.refresh_from_db();task.refresh_from_db()
        self.assertTrue(old.is_interviewer);self.assertFalse(old.needs_followup)
        self.assertEqual(old.notes,'حفظ یادداشت')
        self.assertEqual(old.calls.get().notes,'حفظ تماس')
        self.assertEqual(wrong.workflow_version,1)
        self.assertIsNone(wrong.registration_completed_at)
        self.assertEqual(task.status,'cancelled')

    def test_identity_edit_cannot_apply_customer_fields(self):
        response=self.client.post(reverse('customers:detail',args=[self.person.pk]),{'name':'نام ویرایش‌شده','mobile':'09121112244','notes':'نباید ذخیره شود','needs_followup':'on'})
        self.assertEqual(response.status_code,302)
        self.person.refresh_from_db()
        self.assertEqual(self.person.name,'نام ویرایش‌شده')
        self.assertFalse(self.person.notes)
        self.assertFalse(self.person.needs_followup)

    def test_known_candidate_lookup_returns_recruitment_route_without_sales_analysis(self):
        data=self.client.get(reverse('customers:hub_check_api'),{'mobile':self.person.mobile}).json()
        self.assertTrue(data['is_interviewer'])
        self.assertIn('/customers/',data['profile_url'])
        self.assertNotIn('customer_analysis',data)

    def test_advanced_candidate_registration_denial_is_enforced(self):
        user=User.objects.create_user('no_candidate_add')
        UserPermissionOverride.objects.create(user=user,permission_key='calls.add',granted=True)
        UserPermissionOverride.objects.create(user=user,permission_key='customers.candidate_add',granted=False)
        self.client.force_login(user)
        response=self.client.post(reverse('customers:hub_submit_call'),{'name':'فرد جدید','mobile':'09129991122','is_interviewer':'on'})
        self.assertEqual(response.status_code,403)
        self.assertFalse(Customer.objects.filter(mobile='09129991122').exists())

    def test_admin_does_not_reopen_customer_operations_for_candidates(self):
        response=self.client.get('/admin/customers/customer/'+str(self.person.pk)+'/change/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'هویت مصاحبه‌کننده')
        self.assertNotContains(response,'name="notes"')
        self.assertNotContains(response,'name="source"')
        response=self.client.post('/admin/calls/call/add/',{'customer':self.person.pk,'call_number':self.person.mobile})
        self.assertEqual(response.status_code,403)
