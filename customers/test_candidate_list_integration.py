from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import UserPermissionOverride
from .models import Customer,Reception


class CandidateListIntegrationTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_superuser('merged_admin')
        self.client.force_login(self.admin)
        self.hub=reverse('customers:hub')
        self.fresh=Customer.objects.create(name='ثبت اولیه',mobile='09126660001',is_interviewer=True,assigned_to=self.admin)
        self.admitted=Customer.objects.create(name='دارای پذیرش',mobile='09126660002',is_interviewer=True,assigned_to=self.admin)
        self.visit=Reception.objects.create(customer=self.admitted,person_type='interviewer',arrived_at=timezone.now())
        self.ordinary=Customer.objects.create(name='مشتری',mobile='09126660003',assigned_to=self.admin)

    def test_shared_hub_layout_has_contextual_rows_and_actions(self):
        response=self.client.get(self.hub,{'tab':'info','people':'candidates'})
        self.assertEqual(response.status_code,200)
        self.assertTemplateUsed(response,'customers/hub.html')
        self.assertTemplateUsed(response,'customers/hub_table_partial.html')
        self.assertTrue(response.context['candidate_mode'])
        rows={person.pk:person for person in response.context['customers']}
        self.assertEqual(set(rows),{self.fresh.pk,self.admitted.pk})
        self.assertFalse(rows[self.fresh.pk].candidate_reception_id)
        self.assertEqual(rows[self.admitted.pk].candidate_reception_id,self.visit.pk)
        self.assertContains(response,'ثبت پذیرش')
        self.assertContains(response,'پرونده مصاحبه‌کننده')
        self.assertNotContains(response,'بازگشت به صفحه اطلاعات')

    def test_partial_search_and_pagination_keep_candidate_mode_without_sales_actions(self):
        for i in range(11):Customer.objects.create(name='نمونه '+str(i),mobile='09126661'+str(i).zfill(3),is_interviewer=True,assigned_to=self.admin)
        response=self.client.get(self.hub,{'tab':'info','people':'candidates','page':2},HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(len(response.context['customers']),3)
        self.assertContains(response,'people=candidates')
        self.assertNotContains(response,'openQuickCall(')
        self.assertNotContains(response,'منبع جذب')
        self.assertNotContains(response,'وضعیت پیگیری')
        response=self.client.get(self.hub,{'tab':'info','people':'candidates','q':self.fresh.mobile,'visit':'registered'})
        self.assertEqual([p.pk for p in response.context['customers']],[self.fresh.pk])

    def test_customer_mode_keeps_original_rows_and_old_candidate_url_is_compatible(self):
        response=self.client.get(self.hub,{'tab':'info'})
        self.assertEqual({p.pk for p in response.context['customers']},{self.ordinary.pk,self.fresh.pk,self.admitted.pk})
        response=self.client.get(reverse('customers:candidate_list'))
        self.assertTemplateUsed(response,'customers/hub.html')
        self.assertTrue(response.context['candidate_mode'])

    def test_mode_switch_does_not_bypass_candidate_permission_or_ownership(self):
        user=User.objects.create_user('limited_candidate_mode')
        for key in ('customers.info','customers.candidate_view'):UserPermissionOverride.objects.create(user=user,permission_key=key,granted=True)
        self.client.force_login(user)
        response=self.client.get(self.hub,{'tab':'info','people':'candidates'})
        self.assertEqual(response.context['customers'].paginator.count,0)
        user.permission_overrides.filter(permission_key='customers.candidate_view').update(granted=False)
        self.assertEqual(self.client.get(self.hub,{'tab':'info','people':'candidates'}).status_code,403)

    def test_unified_search_returns_both_types_with_their_own_actions(self):
        self.fresh.name='مشترک مصاحبه';self.fresh.save(update_fields=['name'])
        self.ordinary.name='مشترک مشتری';self.ordinary.save(update_fields=['name'])
        for mode in ('', 'candidates'):
            response=self.client.get(self.hub,{'tab':'info','people':mode,'q':'مشترک','search_all':'1'})
            self.assertEqual({p.pk for p in response.context['customers']},{self.fresh.pk,self.ordinary.pk})
            self.assertTrue(response.context['unified_search'])
            self.assertContains(response,'ثبت پذیرش')
            self.assertContains(response,'name="search_all" value="1"')
            candidate=next(p for p in response.context['customers'] if p.is_interviewer)
            self.assertFalse(hasattr(candidate,'history_calls'))

    def test_unified_search_respects_candidate_denial_and_ownership(self):
        user=User.objects.create_user('common_search_user')
        for key in ('customers.info','customers.candidate_view'):
            UserPermissionOverride.objects.create(user=user,permission_key=key,granted=True)
        self.client.force_login(user)
        params={'tab':'info','q':self.fresh.mobile,'search_all':'1'}
        self.assertEqual(self.client.get(self.hub,params).context['customers'].paginator.count,0)
        self.fresh.assigned_to=user;self.fresh.save(update_fields=['assigned_to'])
        self.assertEqual(self.client.get(self.hub,params).context['customers'].paginator.count,1)
        user.permission_overrides.filter(permission_key='customers.candidate_view').update(granted=False)
        self.assertEqual(self.client.get(self.hub,params).context['customers'].paginator.count,0)
