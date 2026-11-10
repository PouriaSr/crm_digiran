from datetime import timedelta
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth.models import Group, User
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.forms import UserCreateForm
from accounts.models import UserPermissionOverride
from accounts.permissions import get_user_permissions, has_permission
from ads.models import AdPlatform, AdProcess, AdSource
from calls.models import Call
from customers.models import Customer, Reception
from products.models import Category


class InformationPaginationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin=User.objects.create_superuser('paging-admin')
        cls.manager=User.objects.create_user('paging-supervisor')
        cls.manager.groups.add(Group.objects.get_or_create(name='سرپرست')[0])
        cls.sales=User.objects.create_user('paging-sales')
        cls.sales.groups.add(Group.objects.get_or_create(name='کارشناس فروش')[0])
        cls.hub=reverse('customers:hub')
        cls.cards=[]
        for index in range(23):
            card=Customer.objects.create(name=f'صفحه مشتری {index:02}',mobile=f'0912000{index:04}',assigned_to=cls.manager if index<13 else cls.sales)
            cls.cards.append(card)
        cls.deleted=Customer.objects.create(name='مشتری غیرفعال آزمون',mobile='09129999999',assigned_to=cls.sales)
        cls.deleted.delete()

    def setUp(self):
        self.client.force_login(self.admin)

    def test_newest_is_default_in_query_and_filter_and_all_pages_are_accessible(self):
        expected=list(Customer.all_objects.order_by('-created_at','-pk').values_list('pk',flat=True))
        seen=[]
        for number,size in [(1,10),(2,10),(3,4)]:
            response=self.client.get(self.hub,{'tab':'info','page':number})
            page=response.context['customers']
            self.assertEqual(len(page),size)
            self.assertEqual(page.paginator.per_page,10)
            self.assertEqual(response.context['table_filters']['date_field'],'created')
            self.assertNotContains(response,'name="display_mode"')
            seen.extend(card.pk for card in page)
        self.assertEqual(seen,expected)
        response=self.client.get(self.hub,{'sort':'bad'})
        self.assertEqual(response.context['table_filters']['date_field'],'created')

    def test_expert_filter_matches_column_preserves_search_and_order_across_pages(self):
        query={'tab':'info','contact_expert':self.manager.pk,'q':'صفحه'}
        first=self.client.get(self.hub,query)
        self.assertEqual(list(first.context['customers']),list(reversed(self.cards[:13]))[:10])
        self.assertContains(first,'contact_expert='+str(self.manager.pk))
        self.assertNotContains(first,'name="sort"')
        second=self.client.get(self.hub,{**query,'page':2})
        self.assertEqual(list(second.context['customers']),list(reversed(self.cards[:13]))[10:])
        self.assertEqual(second.context['customers'].paginator.count,13)
        self.assertEqual(self.client.get(self.hub,{'contact_expert':'invalid'}).context['customers'].paginator.count,0)
        self.assertEqual(self.client.get(self.hub,{'contact_expert':'unassigned'}).context['customers'].paginator.count,0)

    def test_call_histories_have_independent_pages_beyond_tenth_record(self):
        card=self.cards[-1]
        Call.objects.bulk_create([Call(customer=card,caller_name=card.name,call_number=card.mobile,called_by=self.admin) for _ in range(23)])
        response=self.client.get(self.hub,{'q':card.mobile,f'contact_{card.pk}_page':3})
        history=list(response.context['customers'])[0].history_calls
        self.assertEqual(len(history),3)
        self.assertEqual(history.paginator.count,23)
        response=self.client.get(reverse('customers:detail',args=[card.pk]),{'calls_page':2})
        self.assertEqual(len(response.context['calls']),10)
        self.assertContains(response,'calls_page=3')

    def test_definition_lists_and_workflow_use_ten_records_per_page(self):
        for index in range(13):
            Category.objects.create(name=f'گروه {index}',slug=f'page-{index}')
            platform=AdPlatform.objects.create(name=f'عنوان {index}')
            AdProcess.objects.create(platform=platform,name=f'فرایند {index}',default_cost=0)
            AdSource.objects.create(phone_number=f'0212000{index:04}')
        for name,key in [('products:category_list','categories'),('ads:platform_list','items'),('ads:process_list','items'),('ads:source_list','items')]:
            first=self.client.get(reverse(name))
            total=first.context[key].paginator.count
            last=first.context[key].paginator.num_pages
            second=self.client.get(reverse(name),{'page':last})
            self.assertEqual(len(first.context[key]),10,name)
            self.assertEqual(len(second.context[key]),(total-1)%10+1,name)
            self.assertContains(first,'page=2')
        for card in self.cards:
            Reception.objects.create(customer=card,person_type='interviewer',referred_at=timezone.now())
        page=self.client.get(self.hub,{'tab':'hiring','hiring_page':3})
        self.assertEqual(len(page.context['hiring_records']),3)
        self.assertEqual(page.context['hiring_records'].paginator.count,23)

    def test_global_search_offers_remaining_records_and_total_count(self):
        response=self.client.get(reverse('dashboard:search'),{'q':'صفحه'})
        self.assertEqual(response.context['results']['total'],23)
        self.assertEqual(len(response.context['results']['customers']),10)
        self.assertContains(response,'customers_page=2')
        response=self.client.get(reverse('dashboard:search'),{'q':'صفحه','customers_page':3})
        self.assertEqual(len(response.context['results']['customers']),3)

    def test_only_supervisor_and_admin_can_access_inactive_data_even_with_allow_override(self):
        UserPermissionOverride.objects.create(user=self.sales,permission_key='customers.delete',granted=True)
        self.client.force_login(self.sales)
        self.assertFalse(has_permission(self.sales,'customers.delete'))
        self.assertNotIn('customers.delete',get_user_permissions(self.sales))
        response=self.client.get(self.hub,{'tab':'info'})
        self.assertNotContains(response,reverse('customers:inactive_list'))
        self.assertFalse(any(card.is_deleted for card in response.context['customers']))
        for name in ('inactive_list','restore'):
            url=reverse('customers:'+name,args=[self.deleted.pk] if name=='restore' else [])
            self.assertEqual(self.client.get(url).status_code,403)
        response=self.client.post(reverse('customers:deactivate',args=[self.cards[0].pk]))
        self.assertEqual(response.status_code,403)
        self.cards[0].refresh_from_db();self.assertFalse(self.cards[0].is_deleted)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse('customers:inactive_list')).status_code,200)
        self.assertContains(self.client.get(reverse('customers:detail',args=[self.cards[0].pk])),reverse('customers:deactivate',args=[self.cards[0].pk]))
        UserPermissionOverride.objects.create(user=self.manager,permission_key='customers.delete',granted=False)
        self.assertFalse(has_permission(self.manager,'customers.delete'))

    def test_advanced_access_cannot_save_out_of_role_grant_and_migration_is_targeted(self):
        form=UserCreateForm(data={'username':'invalid-grant','role':'sales','password1':'test-only-123','password2':'test-only-123','perm__customers_delete':'allow','is_active':'on'})
        self.assertTrue(form.is_valid(),form.errors)
        user=form.save()
        self.assertFalse(user.permission_overrides.filter(permission_key='customers.delete',granted=True).exists())
        self.assertFalse(has_permission(user,'customers.delete'))
        self.assertEqual(form.fields['perm__customers_delete'].widget.attrs['data-allowed-roles'],'admin,sales_manager')
        UserPermissionOverride.objects.create(user=self.sales,permission_key='customers.delete',granted=True)
        keep=UserPermissionOverride.objects.create(user=self.sales,permission_key='customers.hiring',granted=True)
        manager_grant=UserPermissionOverride.objects.create(user=self.manager,permission_key='customers.delete',granted=True)
        migration=import_module('accounts.migrations.0005_restrict_customer_deactivation')
        for _ in range(2):migration.remove_out_of_role_grants(apps,SimpleNamespace(connection=connection))
        self.assertFalse(self.sales.permission_overrides.filter(permission_key='customers.delete',granted=True).exists())
        self.assertTrue(UserPermissionOverride.objects.filter(pk=keep.pk).exists())
        self.assertTrue(UserPermissionOverride.objects.filter(pk=manager_grant.pk).exists())

    def test_admin_lists_use_ten_and_admin_delete_cannot_bypass_role_ceiling(self):
        from django.contrib import admin
        from django.contrib.auth.models import Permission
        from django.test import RequestFactory
        for model_admin in admin.site._registry.values():
            self.assertEqual(model_admin.list_per_page,10)
            self.assertEqual(model_admin.list_max_show_all,10)
        self.sales.user_permissions.add(Permission.objects.get(content_type__app_label='customers',codename='delete_customer'))
        self.assertTrue(self.sales.has_perm('customers.delete_customer'))
        request=RequestFactory().get('/admin/customers/customer/')
        request.user=self.sales
        self.assertFalse(admin.site._registry[Customer].has_delete_permission(request))
