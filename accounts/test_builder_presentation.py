import json
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from accounts.models import SectionSchema,SectionField,SectionColumn,InterfaceComponent
from accounts.builder_presentation import section_preview,editor_groups
from accounts.structure_forms import SectionForm,FieldForm,ColumnForm,StageForm,TransitionForm
from accounts.interface_forms import InterfaceForm
from customers.models import Customer
from hr.models import Task


class BuilderPresentationTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_superuser('builder_admin')
        self.client.force_login(self.admin)
        self.section=SectionSchema.objects.get(key='info')

    def test_preview_uses_definitions_without_business_values_or_side_effects(self):
        customer=Customer.objects.create(name='مشتری محرمانه',mobile='09123335678',assigned_to=self.admin)
        SectionField.objects.create(section=self.section,key='score',label='امتیاز',field_type='decimal',minimum=Decimal('2'),default_value='3')
        SectionColumn.objects.create(section=self.section,key='score',label='ستون امتیاز',source='extra:score',filterable=True)
        before=Task.objects.count()
        response=self.client.get(reverse('accounts:structure_section',args=['info']))
        preview=response.context['builder_preview']
        encoded=json.dumps(preview,default=str,ensure_ascii=False)
        self.assertNotIn(customer.name,encoded)
        self.assertNotIn(customer.mobile,encoded)
        self.assertEqual(preview['columns'][0]['source'],'extra:score')
        self.assertTrue(preview['columns'][0]['filterable'])
        self.assertEqual(next(f for f in preview['fields'] if f['key']=='score')['minimum'],Decimal('2'))
        self.assertEqual(Task.objects.count(),before)
        self.assertEqual(self.section.records.count(),0)

    def test_editor_groups_keep_all_visible_controls_exactly_once(self):
        editors={'section':SectionForm(instance=self.section),'field':FieldForm(section=self.section),
                 'column':ColumnForm(section=self.section),'stage':StageForm(section=self.section),
                 'transition':TransitionForm(section=self.section),'component':InterfaceForm(instance=InterfaceComponent())}
        for kind,form in editors.items():
            with self.subTest(kind=kind):
                names=[field.name for group in editor_groups(form,kind) for field in group['fields']]
                self.assertCountEqual(names,[field.name for field in form if not field.is_hidden])
                self.assertEqual(len(names),len(set(names)))

    def test_advanced_validation_errors_are_visible_in_open_group(self):
        form=FieldForm({'label':'ورودی','field_type':'integer','enabled':'on','minimum':'9','maximum':'2','position':'100','revision':'0'},section=self.section)
        self.assertFalse(form.is_valid())
        advanced=[g for g in editor_groups(form,'field') if g['advanced']]
        self.assertTrue(advanced[0]['open'])

    def test_scoped_custom_components_and_overridden_labels_appear_in_own_editor(self):
        custom=InterfaceComponent.objects.create(key='custom.builder.demo',kind='button',label='دکمه همین بخش',custom=True,scope_key='info')
        other=InterfaceComponent.objects.create(key='custom.builder.foreign',kind='button',label='دکمه بخش دیگر',custom=True,scope_key='products')
        response=self.client.get(reverse('accounts:structure_section',args=['info']))
        keys={item['key'] for item in response.context['related_components']}
        self.assertIn(custom.key,keys)
        self.assertNotIn(other.key,keys)
        self.assertContains(response,reverse('accounts:interface_edit',args=[custom.key]))

    def test_successful_edit_returns_to_its_panel_with_updated_preview(self):
        response=self.client.post(reverse('accounts:structure_element_create',args=['info','field']),
            {'label':'عنوان تازه','field_type':'text','enabled':'on','position':'100','revision':'0'})
        self.assertEqual(response.status_code,302)
        self.assertTrue(response.url.endswith('?saved=1#section-fields'))
        after=self.client.get(response.url)
        self.assertTrue(any(item['label']=='عنوان تازه' for item in after.context['builder_preview']['fields']))
        self.assertContains(after,'تغییرات ذخیره شد')

    def test_settings_and_links_are_only_for_admin_and_supervisor(self):
        from django.contrib.auth.models import Group
        from django.test import RequestFactory
        from accounts.permissions import ROLE_TO_GROUP,get_user_permissions
        from accounts.models import UserPermissionOverride
        from accounts.interface import interface_context
        link=InterfaceComponent.objects.create(key='custom.builder.settings',label='ورود به تنظیمات',kind='button',custom=True,url='/accounts/settings/')
        urls=[reverse('accounts:interface_settings'),reverse('accounts:structure_create'),
              reverse('accounts:structure_section',args=['info']),reverse('accounts:structure_element_create',args=['info','field']),
              reverse('accounts:interface_create')]
        for role in ('sales','support','accountant','operator','secretary','ads_manager','sales_manager'):
            with self.subTest(role=role):
                user=User.objects.create_user('builder_'+role)
                user.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP[role])[0])
                for permission in ('system.configure','system.schema','system.workflow'):
                    UserPermissionOverride.objects.create(user=user,permission_key=permission,granted=True)
                self.client.force_login(user)
                manager=role=='sales_manager'
                for url in urls:
                    self.assertEqual(self.client.get(url).status_code,200 if manager else 403)
                if not manager:
                    self.assertEqual(self.client.post(urls[2],{'label':'غیرمجاز'}).status_code,403)
                    self.assertNotIn('system.configure',get_user_permissions(user))
                request=RequestFactory().get('/customers/hub/');request.user=user
                links=interface_context(request)['interface_links']
                self.assertEqual(any(item['key']==link.key for item in links),manager)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(urls[0]).status_code,200)

    def test_settings_links_respect_mount_prefix_and_builtin_destinations(self):
        from accounts.interface import interface_context,settings_destination
        from django.test import RequestFactory
        from django.contrib.auth.models import Group
        from accounts.permissions import ROLE_TO_GROUP
        self.assertTrue(settings_destination('/test/accounts/settings/sections/info/'))
        self.assertTrue(settings_destination('/test/accounts/%73ettings/'))
        self.assertFalse(settings_destination('/customers/hub/?next=/accounts/settings/'))
        user=User.objects.create_user('builder_redirect_sales')
        user.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['sales'])[0])
        from accounts.interface import catalog
        key=next(key for key,value in catalog().items() if value['kind']=='button')
        InterfaceComponent.objects.create(key=key,label='تنظیم',kind='button',behavior={'action_kind':'navigate','destination':'/test/accounts/settings/'})
        request=RequestFactory().get('/customers/hub/');request.user=user
        self.assertFalse(next(item for item in interface_context(request)['interface_overrides'] if item['key']==key)['visible'])
