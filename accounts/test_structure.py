from decimal import Decimal
from django.contrib.auth.models import User,Group
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from accounts.models import SectionSchema,SectionField,SectionColumn,SectionStage,SectionTransition,SectionRecord,SectionRecordEvent,InterfaceComponent,InterfaceChange,UserPermissionOverride
from accounts.structure_service import RecordForm,save_record,transition_record,schema
from accounts.permissions import ROLE_TO_GROUP
from customers.models import Customer
from products.models import Product,Category
from hr.models import Task,TaskNotice,TaskEvent


class StructureBuilderTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_superuser('structure_admin')
        self.sales=User.objects.create_user('structure_sales')
        self.sales.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['sales'])[0])
        self.other=User.objects.create_user('structure_other')
        self.info=SectionSchema.objects.get(key='info')
        self.products=SectionSchema.objects.get(key='products')
        self.client.force_login(self.admin)

    def create_field(self,section=None,**kwargs):
        return SectionField.objects.create(section=section or self.info,key='rating',label='امتیاز',field_type='integer',**kwargs)

    def test_editor_is_scoped_and_rejects_foreign_elements(self):
        own=self.create_field();foreign=self.create_field(self.products)
        page=self.client.get(reverse('accounts:structure_section',args=['info']))
        self.assertContains(page,'فرم و فیلدهای اطلاعات')
        self.assertContains(page,reverse('accounts:structure_element_edit',args=['info','field',own.pk]))
        self.assertNotContains(page,reverse('accounts:structure_element_edit',args=['products','field',foreign.pk]))
        self.assertEqual(self.client.get(reverse('accounts:structure_element_edit',args=['info','field',foreign.pk])).status_code,404)
        product_key='ui.products.form.h12'
        self.assertEqual(self.client.get(reverse('accounts:interface_edit',args=[product_key]),{'scope':'info'}).status_code,403)
        self.client.force_login(self.sales)
        UserPermissionOverride.objects.create(user=self.sales,permission_key='system.configure',granted=True)
        self.assertEqual(self.client.get(reverse('accounts:structure_section',args=['info'])).status_code,403)

    def test_real_customer_registration_validates_and_persists_custom_data(self):
        field=self.create_field(required=True,minimum=Decimal('1'),maximum=Decimal('10'))
        url=reverse('customers:hub_submit_call')
        basic={'name':'ثبت ساختاری','mobile':'09123334445','is_interviewer':'on'}
        self.client.post(url,basic)
        self.assertFalse(Customer.objects.filter(mobile=basic['mobile']).exists())
        self.client.post(url,{**basic,'extra_rating':'99'})
        self.assertFalse(Customer.objects.filter(mobile=basic['mobile']).exists())
        self.client.post(url,{**basic,'extra_rating':'7'})
        customer=Customer.objects.get(mobile=basic['mobile'])
        record=SectionRecord.objects.get(section=self.info,object_id=customer.pk)
        self.assertEqual(record.data,{'rating':7})
        self.assertTrue(SectionRecordEvent.objects.filter(record=record).exists())
        self.assertTrue(Task.objects.filter(source_type='admission',source_customer=customer).exists())
        form=self.client.get(reverse('customers:hub'),{'tab':'info'}).context['call_form']
        self.assertIn('extra_rating',form.fields)
        self.assertEqual(form['extra_rating'].id_for_label,'structure_rating')

    def test_model_form_saves_extras_after_commit_false_and_does_not_cross_sections(self):
        field=self.create_field(self.products,required=True)
        from products.forms import ProductForm
        category=Category.objects.create(name='ساختار',slug='structure')
        form=ProductForm({'category':category.pk,'unit':Product.UNIT_CHOICES[0][0],'name':'کالای ساختاری','code':'STRUCT-01','price':'100','cost_price':'50','stock':'4','min_stock':'1','is_active':'on','extra_rating':'6'},structure_scope='products')
        self.assertTrue(form.is_valid(),form.errors)
        product=form.save(commit=False)
        self.assertFalse(SectionRecord.objects.filter(section=self.products).exists())
        product.save()
        self.assertEqual(SectionRecord.objects.get(section=self.products,object_id=product.pk).data['rating'],6)
        from customers.forms import HubCallForm
        self.assertNotIn('extra_rating',HubCallForm(structure_scope='info').fields)

    def test_type_change_with_incompatible_old_values_is_atomic(self):
        field=SectionField.objects.create(section=self.info,key='codeword',label='کد',field_type='text')
        customer=Customer.objects.create(name='قدیمی',mobile='09123334446',assigned_to=self.admin)
        record=SectionRecord.objects.create(section=self.info,content_type=ContentType.objects.get_for_model(customer),object_id=customer.pk,data={'codeword':'متن غیر عددی'},owner=self.admin)
        url=reverse('accounts:structure_element_edit',args=['info','field',field.pk])
        response=self.client.post(url,{'label':'کد','field_type':'integer','enabled':'on','position':'1','revision':'1'})
        self.assertContains(response,'با داده قبلی سازگار نیست')
        field.refresh_from_db();record.refresh_from_db()
        self.assertEqual(field.field_type,'text');self.assertEqual(record.data['codeword'],'متن غیر عددی')

    def test_archiving_field_keeps_legacy_values(self):
        field=self.create_field()
        record=SectionRecord.objects.create(section=self.info,owner=self.admin,data={'rating':9})
        self.client.post(reverse('accounts:structure_element_archive',args=['info','field',field.pk]),{'revision':field.revision})
        field.refresh_from_db();record.refresh_from_db()
        self.assertFalse(field.enabled);self.assertEqual(record.data['rating'],9)
        self.assertNotIn('extra_rating',RecordForm(section=self.info,user=self.admin).fields)

    def test_configured_filters_search_sort_and_page_size_change_real_query(self):
        self.create_field()
        SectionColumn.objects.create(section=self.info,key='rating_col',label='امتیاز',source='extra:rating',filterable=True,searchable=True)
        a=Customer.objects.create(name='ردیف اول',mobile='09123334447',assigned_to=self.admin)
        b=Customer.objects.create(name='ردیف دوم',mobile='09123334448',assigned_to=self.admin)
        for subject,value in [(a,3),(b,8)]:save_record(self.info,{'rating':value},self.admin,subject=subject)
        url=reverse('customers:hub')
        filtered=self.client.get(url,{'tab':'info','sf_rating_col':'3'})
        self.assertEqual([row.pk for row in filtered.context['customers']],[a.pk])
        self.info.sort_source='extra:rating';self.info.descending=False;self.info.page_size=5;self.info.save()
        response=self.client.get(url,{'tab':'info'})
        self.assertEqual([row.pk for row in response.context['customers']],[a.pk,b.pk])
        self.assertEqual(response.context['customers'].paginator.per_page,5)
        self.assertEqual(response.context['structure_list_payload']['row_kind'],'customer')
        self.assertEqual(response.context['structure_list_payload']['rows'][str(a.pk)]['values']['rating_col'],3)
        invalid=self.client.get(url,{'sf_rating_col':'bad'})
        self.assertEqual(invalid.context['customers'].paginator.count,0)
        self.assertTrue(invalid.context['structure_filter_form'].errors)

    def test_column_source_and_stage_bindings_cannot_escape_section(self):
        field=self.create_field()
        url=reverse('accounts:structure_element_create',args=['info','column'])
        response=self.client.post(url,{'label':'ستون نامعتبر','source':'native:password','enabled':'on','width':'140','align':'center','display':'text','position':'1','revision':'0'})
        self.assertEqual(response.status_code,200);self.assertEqual(self.info.columns.count(),0)
        own=SectionStage.objects.create(section=self.info,label='مبدأ')
        foreign=SectionStage.objects.create(section=self.products,label='مقصد بی‌ربط')
        response=self.client.post(reverse('accounts:structure_element_create',args=['info','transition']),{'source':own.pk,'target':foreign.pk,'label':'غیرمجاز','enabled':'on','revision':'0'})
        self.assertEqual(response.status_code,200);self.assertEqual(self.info.transitions.count(),0)

    def test_workflow_creates_tasks_and_finishes_only_on_valid_transition(self):
        section=SectionSchema.objects.create(key='custom-work',label='فرآیند تیم',custom=True,permission='hr.report_tasks')
        field=SectionField.objects.create(section=section,key='result',label='نتیجه',field_type='text')
        first=SectionStage.objects.create(section=section,label='بررسی',initial=True,create_task=True)
        last=SectionStage.objects.create(section=section,label='تأیید نهایی',status='done',required_fields=['result'])
        action=SectionTransition.objects.create(section=section,source=first,target=last,label='تأیید',require_note=True,roles=['sales'])
        record=save_record(section,{},self.sales,title='کار واقعی')
        task=Task.objects.get(source_type='structure',source_id=record.pk)
        self.assertEqual(task.status,'pending');self.assertTrue(TaskNotice.objects.filter(task=task,user=self.sales).exists())
        self.client.force_login(self.sales)
        row=next(row for row in self.client.get(reverse('hr:task_inbox')).json()['items'] if row['task']==task.pk)
        self.assertEqual(row['action_url'],reverse('accounts:structure_record',args=[section.key,record.pk]))
        with self.assertRaises(ValidationError):transition_record(record,action,self.sales,record.revision,'انجام شد')
        task.refresh_from_db();self.assertEqual(task.status,'pending')
        record=save_record(section,{'result':'نتیجه معتبر'},self.sales,record=record,revision=record.revision)
        with self.assertRaises(ValidationError):transition_record(record,action,self.sales,record.revision,'')
        record=transition_record(record,action,self.sales,record.revision,'بررسی و تأیید شد')
        task.refresh_from_db();self.assertEqual(task.status,'done');self.assertEqual(record.stage,last)
        before=task.events.count()
        with self.assertRaises(ValidationError):transition_record(record,action,self.sales,record.revision-1,'تکرار')
        self.assertEqual(task.events.count(),before)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('accounts:structure_record',args=[section.key,record.pk])).status_code,403)

    def test_native_process_gate_is_enforced_server_side(self):
        self.info.gate_save=True;self.info.save()
        customer=Customer.objects.create(name='مرحله اجباری',mobile='09123334449',assigned_to=self.admin)
        first=SectionStage.objects.create(section=self.info,label='بررسی پیش از ثبت',initial=True)
        last=SectionStage.objects.create(section=self.info,label='آماده',status='done')
        record=save_record(self.info,{},self.admin,subject=customer)
        response=self.client.post(reverse('customers:hub_submit_call'),{'mobile':customer.mobile})
        self.assertEqual(response.status_code,409)
        action=SectionTransition.objects.create(section=self.info,source=first,target=last,label='آماده ثبت')
        transition_record(record,action,self.admin,record.revision)
        response=self.client.post(reverse('customers:hub_submit_call'),{'mobile':customer.mobile})
        self.assertNotEqual(response.status_code,409)

    def test_native_private_fields_are_not_exposed_by_configured_columns(self):
        SectionColumn.objects.create(section=self.info,key='private_email',label='ایمیل',source='native:email')
        customer=Customer.objects.create(name='حریم خصوصی',mobile='09123334450',email='private@example.invalid',assigned_to=self.admin)
        self.client.force_login(self.sales)
        page=self.client.get(reverse('customers:hub'))
        self.assertNotContains(page,'private@example.invalid')

    def test_custom_section_record_crud_is_real_and_scoped(self):
        section=SectionSchema.objects.create(key='custom-docs',label='پرونده سفارشی',custom=True)
        field=SectionField.objects.create(section=section,key='phone',label='شماره',field_type='text',required=True)
        self.client.post(reverse('accounts:structure_record_create',args=[section.key]),{'title':'پرونده نمونه','revision':'0','extra_phone':'123'})
        record=SectionRecord.objects.get(section=section)
        self.assertEqual(record.data['phone'],'123')
        response=self.client.post(reverse('accounts:structure_record',args=[section.key,record.pk]),{'title':'ویرایش','revision':'1','extra_phone':'456'})
        self.assertEqual(response.status_code,302)
        record.refresh_from_db();self.assertEqual(record.data['phone'],'456')
        response=self.client.post(reverse('accounts:structure_record',args=[section.key,record.pk]),{'title':'قدیمی','revision':'1','extra_phone':'789'})
        self.assertContains(response,'هم‌زمان')
        record.refresh_from_db();self.assertEqual(record.data['phone'],'456')

    def test_date_choice_labels_and_readonly_fields_have_real_server_validation(self):
        section=SectionSchema.objects.create(key='custom-types',label='نوع داده',custom=True)
        SectionField.objects.create(section=section,key='date',label='تاریخ',field_type='date',required=True)
        SectionField.objects.create(section=section,key='result',label='نتیجه',field_type='choice',choices=[{'value':'ok','label':'تأیید'}],required=True)
        SectionField.objects.create(section=section,key='fixed',label='کد ثابت',field_type='integer',readonly=True,default_value='5')
        form=RecordForm({'extra_date':'1405/08/19','extra_result':'ok','extra_fixed':'999','revision':'0','title':'انواع'},section=section,user=self.admin)
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.values()['fixed'],5)
        self.assertEqual(form.values()['date'],'2026-11-10')
        self.assertEqual(form.values()['result'],'ok')
        invalid=RecordForm({'extra_date':'1405/99/99','extra_result':'forged'},section=section,user=self.admin)
        self.assertFalse(invalid.is_valid());self.assertIn('extra_date',invalid.errors);self.assertIn('extra_result',invalid.errors)

    def test_native_input_rules_validate_length_without_breaking_candidate_flow(self):
        SectionField.objects.create(section=self.info,key='notes_rule',native_name='notes',label='شرح کوتاه',field_type='text',required=True,max_length=4)
        data={'name':'کارجوی مستقل','mobile':'09123334461','is_interviewer':'on'}
        self.client.post(reverse('customers:hub_submit_call'),data)
        self.assertTrue(Customer.objects.filter(mobile=data['mobile']).exists())
        from customers.forms import HubCallForm
        field=HubCallForm(structure_scope='info').fields['notes']
        with self.assertRaises(ValidationError):field.clean('توضیح بیش از چهار حرف')

    def test_archive_restore_custom_records_preserves_values_and_cancels_task(self):
        section=SectionSchema.objects.create(key='custom-archive',label='بایگانی',custom=True)
        stage=SectionStage.objects.create(section=section,label='در انتظار',initial=True,create_task=True)
        record=save_record(section,{'legacy':'keep'},self.admin,title='مورد بایگانی')
        task=Task.objects.get(source_type='structure',source_id=record.pk)
        url=reverse('accounts:structure_record_archive',args=[section.key,record.pk])
        self.client.post(url,{'revision':record.revision})
        record.refresh_from_db();task.refresh_from_db()
        self.assertTrue(record.archived);self.assertEqual(record.data['legacy'],'keep');self.assertEqual(task.status,'cancelled')
        self.client.post(url,{'revision':record.revision,'restore':'1'})
        record.refresh_from_db();task.refresh_from_db()
        self.assertFalse(record.archived);self.assertEqual(task.status,'pending');self.assertEqual(Task.objects.filter(source_type='structure',source_id=record.pk).count(),1)

    def test_failed_http_transition_rolls_back_data_changes(self):
        section=SectionSchema.objects.create(key='custom-atomic',label='تراکنش',custom=True)
        SectionField.objects.create(section=section,key='result',label='نتیجه')
        source=SectionStage.objects.create(section=section,label='شروع',initial=True)
        target=SectionStage.objects.create(section=section,label='پایان',status='done')
        action=SectionTransition.objects.create(section=section,source=source,target=target,label='اقدام',require_note=True)
        record=save_record(section,{'result':'قبلی'},self.admin,title='رکورد')
        response=self.client.post(reverse('accounts:structure_record',args=[section.key,record.pk]),{'extra_result':'تغییر نباید ثبت شود','title':record.title,'revision':record.revision,'transition':action.pk})
        self.assertContains(response,'توضیح انجام اقدام الزامی')
        record.refresh_from_db();self.assertEqual(record.data['result'],'قبلی');self.assertEqual(record.stage,source)

    def test_advanced_structure_and_workflow_denials_are_independent(self):
        manager=User.objects.create_user('schema_supervisor')
        manager.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['sales_manager'])[0])
        UserPermissionOverride.objects.create(user=manager,permission_key='system.workflow',granted=False)
        self.client.force_login(manager)
        self.assertEqual(self.client.get(reverse('accounts:structure_element_create',args=['info','stage'])).status_code,403)
        self.assertEqual(self.client.get(reverse('accounts:structure_element_create',args=['info','field'])).status_code,200)

    def test_native_candidate_denial_still_applies_in_data_editor_and_tasks(self):
        manager=User.objects.create_user('private_schema_manager')
        manager.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['sales_manager'])[0])
        UserPermissionOverride.objects.create(user=manager,permission_key='customers.candidate_view',granted=False)
        candidate=Customer.objects.create(name='کارجوی خصوصی',mobile='09123334462',is_interviewer=True,assigned_to=manager)
        SectionStage.objects.create(section=self.info,label='بررسی خصوصی',initial=True,create_task=True)
        record=save_record(self.info,{},self.admin,subject=candidate)
        task=Task.objects.get(source_type='structure',source_id=record.pk)
        self.assertIsNone(task.assigned_user)
        self.client.force_login(manager)
        self.assertEqual(self.client.get(reverse('accounts:structure_record',args=['info',record.pk])).status_code,403)
        self.assertNotContains(self.client.get(reverse('accounts:structure_data',args=['info'])),'کارجوی خصوصی')

    def test_apply_existing_keeps_values_and_does_not_duplicate_tasks(self):
        SectionField.objects.create(section=self.info,key='legacy',label='کد جدید',field_type='integer',default_value='3')
        SectionStage.objects.create(section=self.info,label='آغاز برای قبلی‌ها',initial=True,create_task=True)
        subject=Customer.objects.create(name='اطلاعات قبلی',mobile='09123334463',assigned_to=self.admin)
        url=reverse('accounts:structure_apply_existing',args=['info'])
        self.client.post(url)
        record=SectionRecord.objects.get(section=self.info,object_id=subject.pk)
        self.assertEqual(record.data['legacy'],3)
        before=Task.objects.filter(source_type='structure').count()
        self.client.post(url)
        self.assertEqual(Task.objects.filter(source_type='structure').count(),before)

    def test_custom_list_payload_and_numeric_sort_use_saved_values(self):
        section=SectionSchema.objects.create(key='custom-numbers',label='اعداد',custom=True,sort_source='extra:amount',descending=False)
        SectionField.objects.create(section=section,key='amount',label='مبلغ',field_type='decimal')
        SectionColumn.objects.create(section=section,key='amount',label='مبلغ',source='extra:amount',filterable=True)
        a=save_record(section,{'amount':'100'},self.admin,title='بزرگ')
        b=save_record(section,{'amount':'9'},self.admin,title='کوچک')
        page=self.client.get(reverse('accounts:structure_data',args=[section.key]))
        self.assertEqual([item['pk'] for item in page.context['records']],[b.pk,a.pk])
        self.assertEqual(page.context['structure_list_payload']['rows'][str(a.pk)]['values']['amount'],'100')

    def test_plain_registration_starts_configured_workflow_without_extra_fields(self):
        stage=SectionStage.objects.create(section=self.info,label='شروع ثبت',initial=True,create_task=True)
        self.client.post(reverse('customers:hub_submit_call'),{'name':'شروع خودکار','mobile':'09123334469','is_interviewer':'on'})
        customer=Customer.objects.get(mobile='09123334469')
        record=SectionRecord.objects.get(section=self.info,object_id=customer.pk)
        self.assertEqual(record.stage,stage)
        self.assertTrue(Task.objects.filter(source_type='structure',source_id=record.pk).exists())

    def test_backfill_preserves_existing_required_values_without_default(self):
        self.create_field(required=True)
        customer=Customer.objects.create(name='مقدار قبلی',mobile='09123334470',assigned_to=self.admin)
        record=save_record(self.info,{'rating':8},self.admin,subject=customer)
        stage=SectionStage.objects.create(section=self.info,label='بررسی قدیمی',initial=True)
        self.client.post(reverse('accounts:structure_apply_existing',args=['info']))
        record.refresh_from_db()
        self.assertEqual(record.data['rating'],8)
        self.assertEqual(record.stage,stage)


    def test_hidden_native_field_preserves_existing_value_on_forged_post(self):
        SectionField.objects.create(section=self.info,key='email_rule',native_name='email',label='ایمیل',field_type='email',enabled=False)
        customer=Customer.objects.create(name='حفظ مقدار',mobile='09123334471',email='kept@example.invalid',assigned_to=self.admin)
        from customers.forms import CustomerForm
        form=CustomerForm({'name':customer.name,'mobile':customer.mobile,'email':'forged@example.invalid'},instance=customer,structure_scope='info')
        form.is_valid()
        self.assertEqual(form.cleaned_data['email'],'kept@example.invalid')
