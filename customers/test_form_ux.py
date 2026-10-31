from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from customers.models import Customer
from products.models import Product


class SharedFormExperienceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin=User.objects.create_superuser('form_experience_admin')
        cls.secretary=User.objects.create_user('form_experience_secretary')
        cls.secretary.groups.add(Group.objects.get_or_create(name='منشی')[0])
        cls.customer=Customer.objects.create(name='مشتری ویرایش فرم',mobile='09121212345',assigned_to=cls.admin,notes='یادداشت قبلی',national_id='1234567891')

    def setUp(self):self.client.force_login(self.admin)

    def test_invalid_product_has_human_error_links_and_preserves_entered_values(self):
        result=self.client.post(reverse('products:create'),{'name':'کالای باقی‌مانده در فرم','code':'KEEP-01','price':'-1','cost_price':0,'stock':2,'unit':'عدد','min_stock':0,'is_active':'on'})
        self.assertEqual(result.status_code,200)
        self.assertFalse(Product.objects.exists())
        self.assertContains(result,'data-form-error-summary')
        self.assertContains(result,'href="#id_price"')
        self.assertContains(result,'کالای باقی‌مانده در فرم')
        self.assertContains(result,'value="KEEP-01"')
        self.assertContains(result,'crm-form-actions')

    def test_limited_customer_form_keeps_existing_private_field_boundary(self):
        self.client.force_login(self.secretary)
        self.customer.assigned_to=self.secretary;self.customer.save(update_fields=['assigned_to'])
        result=self.client.get(reverse('customers:edit',args=[self.customer.pk]),{'is_modal':'1'})
        self.assertEqual(result.status_code,200)
        self.assertContains(result,'role="dialog"')
        self.assertContains(result,'aria-labelledby="customer-modal-title"')
        self.assertContains(result,'name="mobile"')
        self.assertNotContains(result,'name="national_id"')
        self.assertNotContains(result,'name="birth_date"')
        self.assertNotContains(result,'name="assigned_to"')

    def test_customer_edit_contains_existing_values_and_source_condition_hook(self):
        result=self.client.get(reverse('customers:edit',args=[self.customer.pk]))
        self.assertEqual(result.status_code,200)
        self.assertContains(result,self.customer.mobile)
        self.assertContains(result,self.customer.notes)
        self.assertContains(result,'sourceVal = $event.target.value')
        self.assertContains(result,'crm-form-section')
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.national_id,'1234567891')

    def test_all_create_forms_use_shared_controls_and_chart_runtime_is_loaded_once(self):
        for name in ('customers:create','calls:create','products:create','sales:create','accounts:user_create','ads:create','hr:employee_create','hr:task_create','hr:leave_create','hr:attendance_create'):
            with self.subTest(form=name):
                result=self.client.get(reverse(name))
                self.assertEqual(result.status_code,200)
                self.assertContains(result,'data-crm-form')
                self.assertContains(result,'window.CRMForms=')
        result=self.client.get(reverse('ads:list'))
        self.assertEqual(result.content.decode().count('src="https://cdn.jsdelivr.net/npm/apexcharts"'),1)
        self.assertContains(result,'نمایش جدول داده‌ها')
