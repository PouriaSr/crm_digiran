from datetime import timedelta
from importlib import import_module
from django.apps import apps
from django.db import connection
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import SectionSchema,InterfaceComponent,UserPermissionOverride
from customers.models import Customer,Reception,CustomerCase
from hr.models import Task,TaskEvent
from hr.task_automation import backfill,sync_reception


class RegistrationFirstTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_superuser('registration_first')
        self.person=Customer.objects.create(name='نمونه ترتیب جدید',mobile='09127774411',assigned_to=self.admin)
        self.client.force_login(self.admin)

    def test_real_form_completion_unlocks_case_and_revisit_waits_for_both_stages(self):
        rec=Reception.objects.create(customer=self.person,person_type='customer',referred_at=timezone.now(),referred_to=self.admin)
        case_url=reverse('customers:case_save')
        values={'reception':rec.pk,'condition':'cash','job':'private','credit_rank':'A1','quantity':1,'visit_result':'review'}
        self.assertEqual(self.client.post(case_url,values).status_code,409)
        self.assertEqual(self.client.post(reverse('customers:case_open',args=[rec.pk])).status_code,409)
        self.assertEqual(Task.objects.get(source_key=f'registration:{rec.pk}').status,'pending')
        self.assertFalse(Task.objects.filter(source_key=f'case:{rec.pk}').exists())
        response=self.client.post(reverse('customers:registration_form',args=[rec.pk]),{'name':self.person.name,'mobile':self.person.mobile,'stage':'lead','source':'direct','notes':'شرح مشخصات','address':'نشانی نمونه'})
        self.assertEqual(response.status_code,302,response.context['form'].errors if response.status_code!=302 else '')
        self.assertEqual(Task.objects.get(source_key=f'registration:{rec.pk}').status,'done')
        self.assertEqual(Task.objects.get(source_key=f'case:{rec.pk}').status,'pending')
        self.client.post(reverse('customers:reception_action'),{'action':'arrive','customer':self.person.pk,'person_type':'customer'})
        self.assertEqual(self.person.receptions.count(),1)
        self.assertEqual(self.client.post(case_url,values).status_code,302)
        rec.refresh_from_db();self.assertIsNotNone(rec.registration_completed_at);self.assertIsNotNone(rec.case_completed_at)
        self.assertEqual(Task.objects.get(source_key=f'case:{rec.pk}').status,'done')
        self.client.post(reverse('customers:reception_action'),{'action':'arrive','customer':self.person.pk,'person_type':'customer'})
        self.assertEqual(self.person.receptions.count(),2)

    def test_old_premature_case_is_withdrawn_and_registration_keeps_priority_and_deadline(self):
        rec=Reception.objects.create(customer=self.person,person_type='customer')
        old=Task.objects.create(title='پرونده قدیمی',source_type='case',source_id=rec.pk,source_key=f'case:{rec.pk}',source_customer=self.person,assigned_user=self.admin,priority='urgent',due_date=timezone.localdate()+timedelta(days=1))
        Reception.objects.filter(pk=rec.pk).update(referred_at=timezone.now(),referred_to=self.admin)
        reports=set(TaskEvent.objects.filter(report_required=True).values_list('pk',flat=True))
        backfill();backfill();old.refresh_from_db()
        self.assertEqual(old.status,'cancelled')
        current=Task.objects.get(source_key=f'registration:{rec.pk}')
        self.assertEqual(current.priority,'urgent');self.assertEqual(current.due_date,old.due_date)
        self.assertFalse(TaskEvent.objects.filter(report_required=True).exclude(pk__in=reports).exists())
        self.assertEqual(Task.objects.filter(source_key=f'registration:{rec.pk}').count(),1)

    def test_previous_case_completion_and_data_are_preserved_while_profile_is_pending(self):
        stamp=timezone.now()-timedelta(days=1)
        case=CustomerCase.objects.create(customer=self.person,condition='cash',job='private',credit_rank='A1',quantity=1,visit_result='review')
        rec=Reception.objects.create(customer=self.person,person_type='customer',referred_at=stamp,case_completed_at=stamp,case_completed_by=self.admin)
        backfill();rec.refresh_from_db();case.refresh_from_db()
        self.assertEqual(rec.case_completed_at,stamp);self.assertEqual(case.credit_rank,'A1')
        self.assertIsNone(rec.registration_completed_at)
        self.assertEqual(Task.objects.get(source_key=f'registration:{rec.pk}').status,'pending')

    def test_access_policy_swap_includes_denials_advanced_permissions_and_single_tab_override(self):
        # The migration runs once on upgrade. Existing grants follow the exchanged stages.
        swap=import_module('accounts.migrations.0014_swap_registration_case').swap
        user=User.objects.create_user('policy_swap')
        UserPermissionOverride.objects.create(user=user,permission_key='customers.case',granted=True)
        UserPermissionOverride.objects.create(user=user,permission_key='customers.registration',granted=False)
        UserPermissionOverride.objects.create(user=user,permission_key='customers.case_edit',granted=False)
        SectionSchema.objects.filter(key='case').update(position=17,roles=['support'])
        SectionSchema.objects.filter(key='registration').update(position=42,roles=['operator'])
        InterfaceComponent.objects.filter(key__in=['hub.tab.case','hub.tab.registration']).delete()
        InterfaceComponent.objects.create(key='hub.tab.case',kind='tab',label='پرونده',position=17,roles=['support'])
        from types import SimpleNamespace
        swap(apps,SimpleNamespace(connection=connection))
        grants=dict(user.permission_overrides.values_list('permission_key','granted'))
        self.assertEqual(grants,{'customers.registration':True,'customers.case':False,'customers.registration_edit':False})
        self.assertEqual(SectionSchema.objects.get(key='registration').position,17)
        self.assertEqual(SectionSchema.objects.get(key='registration').roles,['support'])
        self.assertEqual(InterfaceComponent.objects.get(key='hub.tab.registration').roles,['support'])
        self.assertEqual(InterfaceComponent.objects.get(key='hub.tab.case').position,42)
