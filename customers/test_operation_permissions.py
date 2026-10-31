from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.urls import reverse
from django.utils import timezone
from accounts.models import UserPermissionOverride
from accounts.permissions import has_permission, get_user_permissions, PERMISSION_PARENT
from customers.models import Customer, Reception, CustomerNote
from calls.models import Call

class OperationPermissionsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin=User.objects.create_superuser('op-admin')
        cls.owner=User.objects.create_user('op-owner');cls.owner.groups.add(Group.objects.get_or_create(name='اپراتور')[0])
        cls.manager=User.objects.create_user('op-manager');cls.manager.groups.add(Group.objects.get_or_create(name='مدیر فروش')[0])
        cls.customer=Customer.objects.create(name='مشتری مجوز',mobile='09121234567',notes='شرح اصلی',assigned_to=cls.owner)
        cls.call=Call.objects.create(customer=cls.customer,caller_name=cls.customer.name,call_number=cls.customer.mobile,notes='تماس اصلی')

    def setUp(self):self.client.force_login(self.owner)
    def permission(self,user,key,value):UserPermissionOverride.objects.update_or_create(user=user,permission_key=key,defaults={'granted':value})

    def test_edit_denial_blocks_both_interfaces_and_direct_post(self):
        for key,url in [('customers.edit',reverse('customers:edit',args=[self.customer.pk])),('calls.edit',reverse('calls:edit',args=[self.call.pk])),('calls.edit',reverse('customers:hub_call_edit',args=[self.call.pk]))]:
            self.permission(self.owner,key,False)
            self.assertEqual(self.client.post(url,{'notes':'تغییر'}).status_code,403)
        self.customer.refresh_from_db();self.call.refresh_from_db()
        self.assertEqual(self.customer.notes,'شرح اصلی');self.assertEqual(self.call.notes,'تماس اصلی')
        page=self.client.get(reverse('customers:hub'))
        self.assertNotContains(page,'aria-label="ویرایش"')
        self.assertNotContains(page,'aria-label="ویرایش تماس"')

    def test_customer_and_call_edit_controls_are_independent(self):
        self.permission(self.owner,'customers.edit',False)
        response=self.client.get(reverse('customers:hub'))
        self.assertNotContains(response,'aria-label="ویرایش"')
        self.assertContains(response,'aria-label="ویرایش تماس"')
        self.assertEqual(self.client.post(reverse('customers:hub_call_edit',args=[self.call.pk]),{'notes':'تماس اصلاحی','status':'answered','purpose':'sale'}).status_code,302)

    def test_manager_transfer_denial_is_effective(self):
        self.client.force_login(self.manager)
        self.permission(self.manager,'calls.reassign',False)
        self.assertEqual(self.client.post(reverse('calls:reassign',args=[self.call.pk]),{'called_by':self.manager.pk}).status_code,403)
        self.assertEqual(self.client.post(reverse('customers:reassign',args=[self.customer.pk]),{'assigned_to':self.manager.pk}).status_code,403)
        self.customer.refresh_from_db();self.assertEqual(self.customer.assigned_to,self.owner)

    def test_custom_edit_grant_does_not_bypass_ownership(self):
        stranger=User.objects.create_user('op-stranger')
        for key in ('customers.edit','calls.edit'):self.permission(stranger,key,True)
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(reverse('customers:edit',args=[self.customer.pk])).status_code,403)
        self.assertEqual(self.client.get(reverse('calls:edit',args=[self.call.pk])).status_code,403)

    def test_new_operation_inherits_existing_override_then_can_be_customized(self):
        for key,parent in PERMISSION_PARENT.items():
            self.permission(self.owner,parent,False)
            self.assertFalse(has_permission(self.owner,key),key)
            self.assertNotIn(key,get_user_permissions(self.owner))
            self.permission(self.owner,key,True)
            self.assertTrue(has_permission(self.owner,key),key)
            self.assertIn(key,get_user_permissions(self.owner))

    def test_read_only_reception_cannot_register_or_refer(self):
        self.permission(self.owner,'customers.reception',True)
        self.permission(self.owner,'customers.reception_add',False)
        self.permission(self.owner,'customers.reception_refer',False)
        url=reverse('customers:reception_action')
        self.assertEqual(self.client.post(url,{'action':'arrive','customer':self.customer.pk,'person_type':'customer'}).status_code,403)
        rec=Reception.objects.create(customer=self.customer,person_type='customer',is_waiting=True,wait_started_at=timezone.now())
        self.assertEqual(self.client.post(url,{'action':'refer','reception':rec.pk,'user':self.manager.pk}).status_code,403)
        page=self.client.get(reverse('customers:hub'),{'tab':'reception'})
        self.assertContains(page,self.customer.name)
        self.assertNotContains(page,'id="arrival-customer"')
        self.assertNotContains(page,'onclick="event.preventDefault(); event.stopPropagation(); openReceptionReferral(this)"')

    def test_read_only_case_and_registration(self):
        self.client.force_login(self.manager)
        rec=Reception.objects.create(customer=self.customer,person_type='customer',referred_at=timezone.now(),case_completed_at=timezone.now())
        self.permission(self.manager,'customers.case_edit',False)
        self.permission(self.manager,'customers.registration_edit',False)
        self.assertEqual(self.client.post(reverse('customers:case_save'),{'reception':rec.pk}).status_code,403)
        self.assertEqual(self.client.get(reverse('customers:registration_form',args=[rec.pk])).status_code,403)
        case=self.client.get(reverse('customers:hub'),{'tab':'case','r':rec.pk})
        self.assertContains(case,self.customer.name);self.assertNotContains(case,'id="case-editor"')
        registration=self.client.get(reverse('customers:hub'),{'tab':'registration'})
        self.assertContains(registration,self.customer.name);self.assertNotContains(registration,'onclick="event.preventDefault(); event.stopPropagation(); openCustomerModal(')

    def test_note_permissions_and_pin_preservation(self):
        note=CustomerNote.objects.create(customer=self.customer,text='یادداشت',created_by=self.owner,is_pinned=True)
        self.permission(self.owner,'customers.notes_pin',False)
        self.assertEqual(self.client.post(reverse('customers:note_toggle_pin',args=[self.customer.pk,note.pk])).status_code,403)
        self.assertEqual(self.client.post(reverse('customers:note_edit',args=[self.customer.pk,note.pk]),{'text':'یادداشت اصلاحی'}).status_code,302)
        note.refresh_from_db();self.assertTrue(note.is_pinned)
        self.permission(self.owner,'customers.notes_delete',False)
        self.assertEqual(self.client.post(reverse('customers:note_delete',args=[self.customer.pk,note.pk])).status_code,403)
        self.assertTrue(CustomerNote.objects.filter(pk=note.pk).exists())

    def test_call_creation_does_not_change_profile_when_edit_denied(self):
        self.permission(self.owner,'customers.edit',False)
        response=self.client.post(reverse('customers:quick_call',args=[self.customer.pk]),{'kind':'new','notes':'تماس تازه'})
        self.assertEqual(response.status_code,302)
        self.customer.refresh_from_db();self.assertEqual(self.customer.notes,'شرح اصلی')
        self.assertTrue(Call.objects.filter(customer=self.customer,notes='تماس تازه').exists())

    def test_analysis_has_explicit_matching_default(self):
        from customers.forms import HubCallForm
        form=HubCallForm(user=self.owner)
        self.assertEqual(form['customer_analysis'].value(),'lead')
        self.assertEqual(dict(form.fields['customer_analysis'].choices)['lead'],'فاقد شرایط')

    def test_personal_profile_denial_hides_fields_and_ignores_spoofed_values(self):
        self.client.force_login(self.manager)
        self.permission(self.manager,'customers.profile_full',False)
        rec=Reception.objects.create(customer=self.customer,person_type='customer',referred_at=timezone.now(),case_completed_at=timezone.now())
        url=reverse('customers:registration_form',args=[rec.pk])
        self.assertNotContains(self.client.get(url),'id="id_address"')
        before=self.customer.address
        response=self.client.post(url,{'name':self.customer.name,'mobile':self.customer.mobile,'source':'direct','notes':'شرح ثبت','address':'آدرس غیرمجاز'})
        self.assertEqual(response.status_code,302)
        self.customer.refresh_from_db();self.assertEqual(self.customer.address,before)
