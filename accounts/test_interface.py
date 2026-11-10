from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.urls import reverse
from accounts.permissions import ROLE_TO_GROUP, has_permission
from accounts.models import InterfaceComponent, InterfaceChange, UserPermissionOverride
from accounts.interface import catalog
from accounts.forms import UserEditForm


class InterfaceSettingsTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_superuser('interface_admin')
        self.manager=User.objects.create_user('interface_manager')
        self.manager.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['sales_manager'])[0])
        self.sales=User.objects.create_user('interface_sales')
        self.sales.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['sales'])[0])
        self.client.force_login(self.admin)
        self.key=next(key for key,meta in catalog().items() if meta['kind']=='column')

    def data(self, **kwargs):
        return {'label':'عنوان جدید','enabled':'on','position':'20','revision':'0',**kwargs}

    def test_only_managers_can_configure_even_with_forced_permission(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse('accounts:interface_settings')).status_code,200)
        UserPermissionOverride.objects.create(user=self.sales,permission_key='system.configure',granted=True)
        self.assertFalse(has_permission(self.sales,'system.configure'))
        self.client.force_login(self.sales)
        for url in ('interface_settings','interface_create'):
            self.assertEqual(self.client.get(reverse('accounts:'+url)).status_code,403)
        self.assertEqual(self.client.post(reverse('accounts:interface_edit',args=[self.key]),self.data()).status_code,403)
        self.assertEqual(InterfaceComponent.objects.count(),0)

    def test_builtin_update_audit_conflict_and_reset(self):
        url=reverse('accounts:interface_edit',args=[self.key])
        self.assertEqual(self.client.post(url,self.data()).status_code,302)
        component=InterfaceComponent.objects.get(key=self.key)
        self.assertEqual(component.label,'عنوان جدید');self.assertEqual(component.revision,1)
        self.assertEqual(InterfaceChange.objects.get().actor,self.admin)
        self.assertContains(self.client.post(url,self.data(label='تغییر قدیمی')), 'هم‌زمان')
        component.refresh_from_db();self.assertEqual(component.label,'عنوان جدید')
        self.assertEqual(self.client.post(reverse('accounts:interface_reset',args=[self.key]),{'revision':'1'}).status_code,302)
        self.assertFalse(InterfaceComponent.objects.exists());self.assertEqual(InterfaceChange.objects.count(),2)

    def test_custom_page_visibility_escaping_and_delete(self):
        self.client.post(reverse('accounts:interface_create'),self.data(kind='tab',body='<script>alert(1)</script>',roles=['sales_manager']))
        item=InterfaceComponent.objects.get(custom=True)
        self.client.force_login(self.manager)
        response=self.client.get(reverse('accounts:interface_page',args=[item.pk]))
        self.assertContains(response,'&lt;script&gt;alert(۱)&lt;/script&gt;')
        self.client.force_login(self.sales)
        self.assertEqual(self.client.get(reverse('accounts:interface_page',args=[item.pk])).status_code,403)
        self.client.force_login(self.admin)
        self.client.post(reverse('accounts:interface_reset',args=[item.key]),{'revision':'1'})
        self.assertEqual(self.client.get(reverse('accounts:interface_page',args=[item.pk])).status_code,404)
        self.assertEqual(InterfaceChange.objects.filter(action='delete').count(),1)

    def test_invalid_links_and_unknown_components_cannot_be_saved(self):
        for link in ('https://evil.example/','//evil.example/','javascript:alert(1)','/\\evil.example/'):
            self.client.post(reverse('accounts:interface_create'),self.data(kind='button',url=link))
            self.assertFalse(InterfaceComponent.objects.exists())
        self.assertEqual(self.client.post(reverse('accounts:interface_edit',args=['not-a-component']),self.data()).status_code,404)

    def test_overrides_do_not_grant_operation_access(self):
        InterfaceComponent.objects.create(key=self.key,kind='column',label='عمومی',roles=['sales'])
        self.client.force_login(self.sales)
        response=self.client.get(reverse('customers:hub'))
        self.assertEqual(response.status_code,200)
        self.assertTrue(next(item for item in response.context['interface_overrides'] if item['key']==self.key)['visible'])
        self.assertEqual(self.client.get(reverse('accounts:user_list')).status_code,403)

    def test_settings_search_pagination_and_advanced_permissions(self):
        response=self.client.get(reverse('accounts:interface_settings'),{'q':self.key})
        self.assertEqual(response.context['components'].paginator.count,1)
        for key in ('system.configure','customers.admission_assign','customers.admission_choose'):
            self.assertIn('perm__'+key.replace('.','_'),UserEditForm(instance=self.manager).fields)

    def test_internal_destinations_respect_cpanel_mount_prefix(self):
        from django.urls import get_script_prefix, set_script_prefix
        from accounts.interface import internal_url
        from accounts.interface_forms import InterfaceForm
        previous=get_script_prefix()
        try:
            set_script_prefix('/test/')
            self.assertEqual(internal_url('/customers/hub/?tab=reception'),'/test/customers/hub/?tab=reception')
            self.assertEqual(internal_url('/test/customers/hub/'),'/test/customers/hub/')
            form=InterfaceForm(self.data(kind='button',url='/customers/hub/',scope_path='/test/customers/hub/'))
            self.assertTrue(form.is_valid(),form.errors)
            self.assertEqual(form.cleaned_data['scope_path'],'/customers/hub/')
        finally:set_script_prefix(previous)
