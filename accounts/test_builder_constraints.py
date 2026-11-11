from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from accounts.models import SectionSchema,SectionField,SectionBehavior
from accounts.behavior_service import rule_capabilities
from accounts.behavior_forms import BehaviorForm
from accounts.structure_forms import SectionForm
from accounts.structure_registry import component_scopes


class BuilderConstraintsTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_superuser('constraints_admin')
        self.client.force_login(self.user)
        self.section=SectionSchema.objects.get(key='info')

    def test_conditions_and_targets_follow_field_type_and_actual_form(self):
        SectionField.objects.create(section=self.section,key='details',label='شرح بیشتر',field_type='text')
        caps=rule_capabilities(self.section)
        self.assertNotIn('gt',caps['purpose']['operators'])
        self.assertNotIn('mobile',caps['purpose']['targets']['hide'])
        self.assertNotIn('source',caps['purpose']['targets']['hide'])
        self.assertNotIn('call_type',caps['purpose']['targets']['optional'])
        self.assertNotIn('email',caps['purpose']['targets']['show'])
        self.assertIn('extra_details',caps['purpose']['targets']['show'])
        self.assertIn('requested_condition',caps['purpose']['targets']['popup'])
        self.assertNotIn('notes',caps['purpose']['targets']['popup'])
        products=rule_capabilities(SectionSchema.objects.get(key='products'))
        self.assertIn('gt',products['price']['operators'])
        self.assertNotIn('price',products['unit']['targets']['clear'])

    def test_unsupported_cross_form_target_and_operator_cannot_be_posted(self):
        data={'source':'purpose','operator':'equals','value':'support','action':'show','target':'email','enabled':'on','position':'100'}
        form=BehaviorForm(data,section=self.section)
        self.assertFalse(form.is_valid());self.assertIn('target',form.errors)
        form=BehaviorForm({**data,'operator':'gt','target':'requested_condition'},section=self.section)
        self.assertFalse(form.is_valid());self.assertIn('operator',form.errors)
        self.assertEqual(SectionBehavior.objects.count(),0)

    def test_section_inventory_deduplicates_fields_and_shows_native_columns(self):
        field=SectionField.objects.create(section=self.section,key='purpose-caption',native_name='purpose',label='عنوان هدف',field_type='choice')
        page=self.client.get(reverse('accounts:structure_section',args=['info']))
        self.assertNotIn(field,list(page.context['fields_list']))
        self.assertEqual(sum(item['name']=='purpose' for item in page.context['native_fields']),1)
        self.assertTrue(page.context['base_columns'])
        self.assertTrue(all(item['kind'] in ('button','link','heading') for item in page.context['related_components']))
        self.assertTrue(all(not item.get('path','').startswith('customers/_interview') for item in page.context['related_components']))
        self.assertEqual(component_scopes('example',{'path':'customers/_interview_modal.html'}),['hiring'])
        self.assertEqual(component_scopes('example',{'path':'customers/_invoice_hub_details.html'}),['invoices'])

    def test_secondary_field_uses_its_real_form_and_irrelevant_settings_are_absent(self):
        page=self.client.get(reverse('accounts:behavior_inspector',args=['info','email']))
        fields=page.context['builder_preview']['fields']
        self.assertTrue(next(f for f in fields if f['key']=='email')['in_primary'])
        self.assertFalse(any(f['key']=='purpose' and f['in_primary'] for f in fields))
        self.assertNotIn('replace_form_logic',SectionForm(instance=SectionSchema.objects.get(key='products')).fields)
        self.assertNotIn('gate_save',SectionForm(instance=SectionSchema.objects.get(key='reception')).fields)

    def test_popup_selector_only_offers_controls_inside_the_button_form(self):
        from accounts.interface_forms import InterfaceForm
        from accounts.models import InterfaceComponent
        form=InterfaceForm(instance=InterfaceComponent(kind='button'),definition={'kind':'button','path':'products/list.html'},scope='products')
        self.assertEqual(list(form.fields['popup_target'].choices),[('', 'فقط نمایش متن')])
        self.assertTrue(form.fields['popup_target'].widget.is_hidden)
        form=InterfaceForm(instance=InterfaceComponent(kind='button'),definition={'kind':'button','path':'products/form.html'},scope='products')
        self.assertIn('unit',dict(form.fields['popup_target'].choices))
        self.assertNotIn('name',dict(form.fields['popup_target'].choices))

    def test_legacy_rule_cannot_hide_essential_field_in_preview_or_form(self):
        from accounts.builder_presentation import section_preview
        from customers.forms import HubCallForm
        rule=SectionBehavior.objects.create(section=self.section,label='قدیمی',source='purpose',value='support',action='hide',target='source')
        preview=section_preview(self.section)
        self.assertFalse(next(r for r in preview['behavior_rules'] if r['id']==str(rule.pk))['enabled'])
        self.assertFalse(any(r['id']==str(rule.pk) for r in HubCallForm(structure_scope='info').structure_behavior_payload['rules']))
        page=self.client.get(reverse('accounts:behavior_inspector',args=['info','purpose']))
        self.assertFalse(page.context['rules'][0].supported)
