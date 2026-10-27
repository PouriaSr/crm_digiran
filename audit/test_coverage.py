"""تست ردیابی Audit برای تماس، پذیرش و پرونده."""
from django.contrib.auth.models import User
from django.test import TestCase

from audit.models import AuditLog
from calls.models import Call
from customers.models import Customer, CustomerCase, Reception


class AuditCoverageTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('aud_admin', password='t123456')
        cls.customer = Customer.objects.create(name='ردیابی', mobile='09120006666',
                                               created_by=cls.user)

    def test_call_is_audited(self):
        before = AuditLog.objects.count()
        call = Call.objects.create(customer=self.customer, caller_name='ردیابی',
                                   call_number='09120006666', contact_type='incoming',
                                   status='answered', called_by=self.user)
        logs = AuditLog.objects.filter(model_name='calls.Call', object_id=call.pk)
        self.assertTrue(logs.exists(), 'ایجاد تماس باید در Audit ثبت شود')
        self.assertGreater(AuditLog.objects.count(), before)

        call.notes = 'یادداشت تازه'
        call.save()
        updated = AuditLog.objects.filter(model_name='calls.Call', object_id=call.pk,
                                          action='updated')
        self.assertTrue(updated.exists(), 'ویرایش تماس باید ثبت شود')

    def test_reception_is_audited(self):
        rec = Reception.objects.create(customer=self.customer, person_type='customer',
                                       has_visit='yes', wait_choice='30')
        self.assertTrue(
            AuditLog.objects.filter(model_name='customers.Reception', object_id=rec.pk).exists(),
            'پذیرش باید در Audit ثبت شود',
        )

    def test_case_is_audited(self):
        case = CustomerCase.objects.create(customer=self.customer, condition='cash',
                                           job='private', credit_rank='B1')
        self.assertTrue(
            AuditLog.objects.filter(model_name='customers.CustomerCase', object_id=case.pk).exists(),
            'پرونده باید در Audit ثبت شود',
        )
