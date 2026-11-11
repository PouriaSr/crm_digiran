from django.test import TestCase
from django.contrib.auth.models import User,Group
from django.urls import reverse
from django.core.exceptions import ValidationError
from accounts.models import SectionSchema,SectionField,SectionBehavior,SectionOption,SectionRecord,SectionColumn,UserPermissionOverride
from accounts.behavior_service import evaluate,effective_options
from accounts.behavior_forms import BehaviorForm
from accounts.permissions import ROLE_TO_GROUP
from customers.models import Customer
from customers.forms import HubCallForm
from ads.models import AdSource
from calls.models import Call
from hr.models import Task


class BehaviorBuilderTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_superuser('behavior_admin')
        self.client.force_login(self.admin)
        self.info=SectionSchema.objects.get(key='info')
        self.source=AdSource.objects.create(label='منبع نمونه',phone_number='09123339991')
        self.basic={'name':'فرد نمونه','mobile':'09123339992','call_type':'incoming','purpose':'sale','call_status':'answered','customer_analysis':'lead','requested_condition':'cash','source':self.source.pk,'notes':'شرح معتبر'}

    def rule(self,**values):
        defaults={'section':self.info,'label':'قاعده','source':'purpose','value':'support','action':'add_tag','argument':'پشتیبانی'}
        defaults.update(values)
        return SectionBehavior.objects.create(**defaults)

    def test_native_option_labels_disable_and_aliases_change_real_registration(self):
        SectionOption.objects.create(section=self.info,field_name='purpose',key='sale',label='عنوان فروش جدید',base_value='sale')
        SectionOption.objects.create(section=self.info,field_name='purpose',key='vip_help',label='پشتیبانی ویژه',base_value='support')
        self.rule(value='vip_help',argument='ویژه')
        form=HubCallForm(structure_scope='info')
        self.assertIn(('vip_help','پشتیبانی ویژه'),list(form.fields['purpose'].choices))
        response=self.client.post(reverse('customers:hub_submit_call'),{**self.basic,'purpose':'vip_help'})
        self.assertEqual(response.status_code,302)
        call=Call.objects.get()
        self.assertEqual(call.purpose,'support')
        record=SectionRecord.objects.get(section=self.info,object_id=call.customer_id)
        self.assertEqual(record.data['_behavior_tags'],['ویژه'])
        self.assertEqual(record.data['_selected_options']['purpose'],'vip_help')
        page=self.client.get(reverse('customers:hub'),{'q':self.basic['mobile']})
        self.assertEqual(page.context['structure_list_payload']['rows'][str(call.customer_id)]['tags'],['ویژه'])
        self.assertContains(self.client.get(reverse('customers:detail',args=[call.customer_id])),'ویژه')

    def test_disabled_native_option_is_rejected_for_new_submissions(self):
        SectionOption.objects.create(section=self.info,field_name='purpose',key='sale',label='فروش',base_value='sale',enabled=False)
        self.client.post(reverse('customers:hub_submit_call'),self.basic)
        self.assertEqual(Call.objects.count(),0)
        self.assertEqual(Customer.objects.count(),0)

    def test_conditional_required_and_show_rules_are_enforced_without_javascript(self):
        field=SectionField.objects.create(section=self.info,key='ticket',label='کد درخواست',field_type='text')
        self.rule(action='show',target='extra_ticket',argument='')
        self.rule(action='require',target='extra_ticket',argument='')
        response=self.client.post(reverse('customers:hub_submit_call'),{**self.basic,'purpose':'support'})
        self.assertEqual(Customer.objects.count(),0)
        self.client.post(reverse('customers:hub_submit_call'),{**self.basic,'purpose':'support','extra_ticket':'REQ-7'})
        self.assertEqual(Call.objects.count(),1)
        self.assertEqual(SectionRecord.objects.get(section=self.info).data['ticket'],'REQ-7')

    def test_hidden_custom_value_cannot_be_forged_and_old_value_is_preserved(self):
        SectionField.objects.create(section=self.info,key='secret',label='اطلاعات',field_type='text')
        self.rule(action='hide',target='extra_secret',argument='')
        self.client.post(reverse('customers:hub_submit_call'),{**self.basic,'purpose':'support','extra_secret':'forged'})
        record=SectionRecord.objects.get(section=self.info)
        self.assertNotEqual(record.data.get('secret'),'forged')

    def test_set_and_clear_actions_and_tag_removal_are_saved(self):
        SectionField.objects.create(section=self.info,key='result',label='نتیجه',field_type='text')
        self.rule(action='set',target='extra_result',argument='اتومات')
        self.rule(action='add_tag',argument='مهم')
        self.client.post(reverse('customers:hub_submit_call'),{**self.basic,'purpose':'support','extra_result':'forged'})
        record=SectionRecord.objects.get(section=self.info)
        self.assertEqual(record.data['result'],'اتومات');self.assertEqual(record.data['_behavior_tags'],['مهم'])
        self.rule(value='sale',action='remove_tag',argument='مهم')
        self.rule(value='sale',action='clear',target='extra_result',argument='')
        self.client.post(reverse('customers:hub_submit_call'),self.basic)
        record.refresh_from_db()
        self.assertEqual(record.data['result'],'');self.assertEqual(record.data['_behavior_tags'],[])

    def test_replacement_mode_can_replace_default_analysis_followup_logic(self):
        self.info.replace_form_logic=True;self.info.save()
        self.rule(source='customer_analysis',value='potential',action='set',target='needs_followup',argument='false')
        self.client.post(reverse('customers:hub_submit_call'),{**self.basic,'customer_analysis':'potential'})
        self.assertEqual(Call.objects.count(),1)
        self.assertFalse(Customer.objects.get().followups.exists())
        self.assertEqual(Customer.objects.get().stage,'potential')

    def test_rules_work_in_another_module_and_preserve_native_choice_type(self):
        from products.models import Category,Product
        from products.forms import ProductForm
        section=SectionSchema.objects.get(key='products')
        category=Category.objects.create(name='گروه',slug='behavior-group')
        base=Product.UNIT_CHOICES[0][0]
        SectionOption.objects.create(section=section,field_name='unit',key='custom_unit',label='واحد سفارشی',base_value=base)
        SectionField.objects.create(section=section,key='note',label='توضیح',field_type='text')
        SectionBehavior.objects.create(section=section,label='توضیح خودکار',source='unit',value='custom_unit',action='set',target='extra_note',argument='ثبت از واحد جدید')
        form=ProductForm({'category':category.pk,'name':'کالای نمونه','code':'BH-1','unit':'custom_unit','price':'10','cost_price':'1','stock':'2','min_stock':'1','is_active':'on'},structure_scope='products')
        self.assertTrue(form.is_valid(),form.errors)
        product=form.save()
        self.assertEqual(product.unit,base)
        self.assertEqual(ProductForm(instance=product,structure_scope='products')['unit'].value(),'custom_unit')
        self.assertEqual(SectionRecord.objects.get(section=section).data['note'],'ثبت از واحد جدید')
        SectionBehavior.objects.create(section=section,label='برچسب فهرست',source='unit',value='custom_unit',action='add_tag',argument='واحد ویژه')
        record=SectionRecord.objects.get(section=section);record.data['_behavior_tags']=['واحد ویژه'];record.save()
        SectionColumn.objects.create(section=section,key='note',label='توضیح',source='extra:note',filterable=True)
        page=self.client.get(reverse('products:list'),{'sf_note':'ثبت از واحد جدید'})
        self.assertEqual(page.context['page_obj'].paginator.count,1)
        self.assertEqual(page.context['structure_list_payload']['rows'][str(product.pk)]['tags'],['واحد ویژه'])
        page=self.client.get(reverse('products:list'),{'sf_note':'مقدار دیگر'})
        self.assertEqual(page.context['page_obj'].paginator.count,0)

    def test_independent_section_options_behaviors_and_filters(self):
        from accounts.structure_service import RecordForm
        section=SectionSchema.objects.create(key='custom-behaviors',label='سفارشی',custom=True)
        SectionField.objects.create(section=section,key='choice',label='نوع',field_type='choice',choices=['a','b'])
        SectionOption.objects.create(section=section,field_name='extra_choice',key='c',label='گزینه تازه')
        SectionBehavior.objects.create(section=section,label='برچسب',source='extra_choice',value='c',action='add_tag',argument='جدید')
        form=RecordForm({'title':'رکورد','revision':'0','extra_choice':'c'},section=section,user=self.admin)
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.values()['choice'],'c');self.assertEqual(form.values()['_behavior_tags'],['جدید'])
        from accounts.structure_service import save_record
        save_record(section,form.values(),self.admin,title='ثبت نمونه')
        SectionColumn.objects.create(section=section,key='type',label='نوع',source='extra:choice',filterable=True)
        page=self.client.get(reverse('accounts:structure_data',args=[section.key]),{'sf_type':'c'})
        self.assertEqual(page.context['records'].paginator.count,1)

    def test_cycle_and_identity_rules_are_rejected(self):
        SectionField.objects.create(section=self.info,key='a',label='الف',field_type='text')
        SectionField.objects.create(section=self.info,key='b',label='ب',field_type='text')
        self.rule(source='extra_a',action='set',target='extra_b',argument='value')
        data={'label':'حلقه','source':'extra_b','operator':'equals','value':'value','action':'set','target':'extra_a','argument':'value','enabled':'on','position':'100','revision':'0'}
        form=BehaviorForm(data,section=self.info)
        self.assertFalse(form.is_valid());self.assertIn('target',form.errors)
        form=BehaviorForm({**data,'target':'mobile'},section=self.info)
        self.assertFalse(form.is_valid());self.assertIn('target',form.errors)

    def test_conditional_choice_restrictions_are_server_validated(self):
        self.rule(action='choices',target='requested_condition',argument='cash')
        self.client.post(reverse('customers:hub_submit_call'),{**self.basic,'purpose':'support','requested_condition':'cheque'})
        self.assertEqual(Call.objects.count(),0)
        self.client.post(reverse('customers:hub_submit_call'),{**self.basic,'purpose':'support','requested_condition':'cash'})
        self.assertEqual(Call.objects.count(),1)

    def test_roles_and_cross_section_edit_access_are_enforced(self):
        self.rule(roles=['sales'])
        self.client.post(reverse('customers:hub_submit_call'),{**self.basic,'purpose':'support'})
        record=SectionRecord.objects.filter(section=self.info).first()
        self.assertFalse(record and record.data.get('_behavior_tags'))
        option=SectionOption.objects.create(section=SectionSchema.objects.get(key='products'),field_name='unit',key='item',label='واحد')
        self.assertEqual(self.client.get(reverse('accounts:behavior_option_edit',args=['info','purpose',option.pk])).status_code,404)
        sales=User.objects.create_user('behavior_sales');sales.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['sales'])[0])
        UserPermissionOverride.objects.create(user=sales,permission_key='system.workflow',granted=True)
        self.client.force_login(sales)
        for name,args in [('behavior_rule_create',['info']),('behavior_inspector',['info','purpose']),('behavior_option_create',['info','purpose']),('behavior_reference_options',['info'])]:
            self.assertEqual(self.client.get(reverse('accounts:'+name,args=args)).status_code,403)

    def test_preview_has_real_options_rules_and_edit_links_without_creating_records(self):
        SectionOption.objects.create(section=self.info,field_name='purpose',key='extra_case',label='گزینه سفارشی',base_value='other')
        self.rule(action='popup',target='requested_condition',argument='یک مورد را انتخاب کنید')
        page=self.client.get(reverse('accounts:structure_section',args=['info']))
        preview=page.context['builder_preview']
        purpose=next(field for field in preview['fields'] if field['key']=='purpose')
        self.assertTrue(any(option['value']=='extra_case' for option in purpose['choices']))
        self.assertTrue(purpose['inspector_url'].endswith('/inputs/purpose/'))
        self.assertEqual(preview['behavior_rules'][0]['action'],'popup')
        self.assertEqual(Call.objects.count(),0);self.assertEqual(SectionRecord.objects.count(),0)

    def test_numeric_and_boolean_rules_are_deterministic(self):
        rules=[{'id':'1','source':'score','operator':'gt','value':'۲','action':'add_tag','target':'','argument':'قبول'}]
        self.assertEqual(evaluate({'score':'۳'},rules)['tags'],['قبول'])
        self.assertEqual(evaluate({'score':'bad'},rules)['tags'],[])

    def test_legacy_tab_alias_keeps_options_and_rules_after_registration_redirect(self):
        SectionOption.objects.create(section=self.info,field_name='purpose',key='alias_support',label='پشتیبانی دلخواه',base_value='support')
        self.rule(value='alias_support')
        page=self.client.get(reverse('customers:hub'),{'tab':'call'})
        self.assertIn(('alias_support','پشتیبانی دلخواه'),list(page.context['call_form'].fields['purpose'].choices))
        self.assertContains(page,'data-form-behavior')
        self.assertEqual(page.context['structure_current'].key,'info')

    def test_option_and_rule_edit_preserve_revision_and_existing_fields(self):
        rule=self.rule()
        page=self.client.get(reverse('accounts:behavior_rule_edit',args=['info',rule.pk]))
        self.assertEqual(page.context['form']['source'].value(),'purpose')
        self.assertEqual(page.context['form']['value'].value(),'support')
        response=self.client.post(reverse('accounts:behavior_rule_edit',args=['info',rule.pk]),{'label':'جدید','source':'purpose','operator':'equals','value':'support','action':'add_tag','argument':'جدید','enabled':'on','position':'100','revision':'0'})
        self.assertContains(response,'هم‌زمان')
        rule.refresh_from_db();self.assertEqual(rule.argument,'پشتیبانی')
        before=SectionOption.objects.count()
        response=self.client.post(reverse('accounts:behavior_option_create',args=['info','purpose']),{'label':'گزینه بد','key':'bad_option','base_value':'invented_path','enabled':'on','position':'10','revision':'0'})
        self.assertEqual(SectionOption.objects.count(),before)
        self.assertEqual(response.status_code,200)

    def test_original_instance_can_keep_a_removed_choice_without_losing_data(self):
        from products.models import Category,Product
        from products.forms import ProductForm
        section=SectionSchema.objects.get(key='products');category=Category.objects.create(name='قدیمی',slug='old-choice')
        base=Product.UNIT_CHOICES[0][0]
        product=Product.objects.create(category=category,name='کالای قبلی',code='OLD-OPTION',unit=base,price=10,cost_price=1,stock=1)
        SectionOption.objects.create(section=section,field_name='unit',key=base,label='واحد قبلی',base_value=base,enabled=False)
        form=ProductForm({'category':category.pk,'name':product.name,'code':product.code,'unit':base,'price':'20','cost_price':'1','stock':'1','min_stock':'1','is_active':'on'},instance=product,structure_scope='products')
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.save().unit,base)

    def test_hard_required_model_fields_cannot_be_cleared_by_rules(self):
        section=SectionSchema.objects.get(key='products')
        form=BehaviorForm({'label':'پاک کردن','source':'unit','operator':'filled','action':'clear','target':'price','enabled':'on','position':'1','revision':'0'},section=section)
        # Price has no nullable representation and cannot be hidden/emptied by configuration.
        self.assertFalse(form.is_valid());self.assertIn('target',form.errors)

    def test_checkbox_conditions_use_boolean_values_and_can_hide_conditional_extra(self):
        SectionField.objects.create(section=self.info,key='default_false',label='پیش‌فرض خاموش',field_type='boolean',default_value='false')
        self.assertIs(HubCallForm(structure_scope='info')['extra_default_false'].value(),False)
        SectionField.objects.create(section=self.info,key='customer_only',label='مختص مشتری',field_type='text',required=True)
        self.rule(source='is_interviewer',value='true',action='hide',target='extra_customer_only',argument='')
        self.client.post(reverse('customers:hub_submit_call'),{'name':'کارجوی نمونه','mobile':'09123338881','is_interviewer':'on'})
        self.assertTrue(Customer.objects.filter(mobile='09123338881').exists())
        self.assertFalse(Call.objects.exists())

    def test_native_option_mapping_is_single_step_even_if_base_option_is_also_edited(self):
        SectionOption.objects.create(section=self.info,field_name='purpose',key='sale',label='گزینه اول',base_value='support')
        SectionOption.objects.create(section=self.info,field_name='purpose',key='support',label='گزینه دوم',base_value='other')
        self.client.post(reverse('customers:hub_submit_call'),self.basic)
        self.assertEqual(Call.objects.get().purpose,'support')

    def test_builtin_button_popup_settings_are_persisted_as_behavior(self):
        from accounts.interface import catalog
        from accounts.structure_registry import component_scopes
        from accounts.models import InterfaceComponent
        key=next(key for key,meta in catalog().items() if meta['kind']=='button' and meta.get('path')=='customers/_call_modal.html' and meta['label']=='ثبت تماس')
        response=self.client.post(reverse('accounts:interface_edit',args=[key])+'?scope=info',{'label':'انتخاب شرایط','enabled':'on','position':'100','revision':'0','action_kind':'popup','popup_text':'شرایط را انتخاب کنید','popup_target':'requested_condition','appearance':'primary'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(InterfaceComponent.objects.get(key=key).behavior['popup_target'],'requested_condition')

    def test_added_option_is_a_valid_default_and_field_remains_editable_with_saved_values(self):
        from accounts.structure_service import RecordForm,save_record
        from accounts.structure_forms import FieldForm
        section=SectionSchema.objects.create(key='custom-choice-edit',label='سفارشی',custom=True)
        field=SectionField.objects.create(section=section,key='type',label='نوع',field_type='choice',choices=['a'])
        SectionOption.objects.create(section=section,field_name='extra_type',key='c',label='گزینه تازه')
        record=save_record(section,{'type':'c'},self.admin,title='قدیمی')
        response=self.client.post(reverse('accounts:structure_element_edit',args=[section.key,'field',field.pk]),{'label':'نوع اصلاح‌شده','field_type':'choice','options':'a','default_value':'c','enabled':'on','position':'100','revision':'1'})
        self.assertEqual(response.status_code,302)
        field.refresh_from_db();record.refresh_from_db()
        self.assertEqual(field.default_value,'c');self.assertEqual(record.data['type'],'c')

    def test_native_added_option_can_be_selected_as_default(self):
        SectionOption.objects.create(section=self.info,field_name='purpose',key='default_support',label='پیش‌فرض پشتیبانی',base_value='support')
        SectionField.objects.create(section=self.info,key='purpose_rule',native_name='purpose',label='هدف',field_type='choice',default_value='default_support')
        form=HubCallForm(structure_scope='info')
        self.assertEqual(form['purpose'].value(),'default_support')
        posted={**self.basic};posted.pop('purpose')
        self.client.post(reverse('customers:hub_submit_call'),posted)
        self.assertEqual(Call.objects.get().purpose,'support')

    def test_multiple_choice_options_and_actions_work_without_scalar_assumptions(self):
        from customers.models import CustomerCase
        from customers.forms import CustomerCaseForm
        section=SectionSchema.objects.get(key='case')
        person=Customer.objects.create(name='پرونده نمونه',mobile='09123337773',assigned_to=self.admin)
        case=CustomerCase.objects.create(customer=person)
        base=CustomerCase.LOAN_CHOICES[0][0]
        SectionOption.objects.create(section=section,field_name='active_loans',key='new_loan',label='وام جدید',base_value=base)
        SectionBehavior.objects.create(section=section,label='انتخاب خودکار',source='condition',operator='equals',value='cash',action='set',target='active_loans',argument='new_loan')
        SectionBehavior.objects.create(section=section,label='برچسب وام',source='active_loans',operator='contains',value='new_loan',action='add_tag',argument='دارای وام')
        data={'condition':'cash','job':CustomerCase.JOB_CHOICES[0][0],'credit_rank':CustomerCase.CREDIT_RANK_CHOICES[0][0],'visit_result':CustomerCase.RESULT_CHOICES[0][0],'quantity':'1'}
        form=CustomerCaseForm(data,instance=case,structure_scope='case')
        self.assertTrue(form.is_valid(),form.errors)
        saved=form.save()
        self.assertEqual(saved.active_loans,[base])
        self.assertEqual(SectionRecord.objects.get(section=section).data['_behavior_tags'],['دارای وام'])
        self.assertEqual(CustomerCaseForm(instance=saved,structure_scope='case')['active_loans'].value(),['new_loan'])
