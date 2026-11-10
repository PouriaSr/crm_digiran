from django.contrib.auth.models import User, Group
from django.test import TestCase
from django.urls import reverse
from accounts.models import UserPermissionOverride
from accounts.permissions import ROLE_TO_GROUP
from customers.models import Customer, Reception
from hr.models import Task, TaskNotice, TaskEvent
from hr.task_automation import backfill
from hr.task_access import visible_tasks


class CustomerAdmissionTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_superuser('customer_admission_admin')
        self.manager=User.objects.create_user('customer_admission_manager')
        self.manager.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['sales_manager'])[0])
        self.sales=User.objects.create_user('customer_admission_sales')
        self.sales.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['sales'])[0])
        self.reception=User.objects.create_user('customer_admission_secretary')
        self.reception.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['secretary'])[0])

    def test_new_customer_and_backfill_receive_task_before_actual_arrival(self):
        person=Customer.objects.create(name='مشتری منتظر',mobile='09124440001',assigned_to=self.sales)
        task=Task.objects.get(source_type='admission',source_customer=person)
        self.assertEqual(task.assigned_user,self.reception)
        self.assertTrue(TaskNotice.objects.filter(task=task,user=self.reception,read_at=None).exists())
        self.assertTrue(visible_tasks(self.reception).filter(pk=task.pk).exists())
        Customer.objects.bulk_create([Customer(name='مشتری قبلی',mobile='09124440002',assigned_to=self.manager)])
        backfill();counts=(Task.objects.count(),TaskEvent.objects.count(),TaskNotice.objects.count());backfill()
        self.assertEqual(counts,(Task.objects.count(),TaskEvent.objects.count(),TaskNotice.objects.count()))
        self.assertEqual(Task.objects.filter(source_type='admission',status='pending').count(),2)
        self.assertEqual(Reception.objects.count(),0)
        self.client.force_login(self.reception)
        self.client.post(reverse('customers:reception_action'),{'action':'arrive','customer':person.pk,'person_type':'customer'})
        task.refresh_from_db();self.assertEqual(task.status,'done')
        self.assertEqual(task.events.get(to_status='done').report_user,self.reception)

    def test_manager_default_is_self_and_choosing_others_requires_permission(self):
        person=Customer.objects.create(name='واگذاری به خود',mobile='09124440003',assigned_to=self.admin)
        self.client.force_login(self.manager)
        response=self.client.get(reverse('customers:hub'))
        self.assertEqual(response.context['admission_default_user'],self.manager)
        url=reverse('customers:admission_assign',args=[person.pk])
        UserPermissionOverride.objects.create(user=self.manager,permission_key='customers.admission_choose',granted=False)
        response=self.client.post(url,{'assigned_to':self.reception.pk})
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.client.post(url,{}).status_code,302)
        person.refresh_from_db();self.assertEqual(person.assigned_to,self.manager)
        self.assertEqual(Task.objects.get(source_type='admission',source_customer=person).assigned_user,self.manager)
        self.client.force_login(self.sales)
        UserPermissionOverride.objects.create(user=self.sales,permission_key='customers.admission_assign',granted=True)
        self.assertEqual(self.client.post(url,{}).status_code,403)
