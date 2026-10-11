"""
تست‌های Global Audit Log — فاز ۸.۴
"""
from django.test import TestCase
from django.contrib.auth.models import User

from customers.models import Customer
from products.models import Product, Category
from .models import AuditLog


class AuditLogBasicTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('auditor', password='t123456')

    def setUp(self):
        AuditLog.objects.all().delete()

    def test_customer_create_logged(self):
        Customer.objects.create(name='علی', mobile='09120000001')
        log = AuditLog.objects.filter(
            model_name='customers.Customer', action='created'
        ).first()
        self.assertIsNotNone(log)
        self.assertIn('علی', log.object_repr)

    def test_customer_update_logged_with_changes(self):
        c = Customer.objects.create(name='علی', mobile='09120000001')
        AuditLog.objects.all().delete()

        c.name = 'علی رضایی'
        c.status = 'active'
        c.save()

        log = AuditLog.objects.filter(
            model_name='customers.Customer', action='updated'
        ).first()
        self.assertIsNotNone(log)
        self.assertIn('name', log.changes)
        self.assertIn('status', log.changes)
        self.assertEqual(log.changes['name']['old'], 'علی')
        self.assertEqual(log.changes['name']['new'], 'علی رضایی')

    def test_customer_delete_logged(self):
        c = Customer.objects.create(name='علی', mobile='09120000001')
        AuditLog.objects.all().delete()

        c.delete()

        log = AuditLog.objects.filter(
            model_name='customers.Customer', action='deleted'
        ).first()
        self.assertIsNotNone(log)

    def test_no_log_when_no_changes(self):
        c = Customer.objects.create(name='علی', mobile='09120000001')
        AuditLog.objects.all().delete()

        c.save()  # بدون تغییر

        self.assertEqual(
            AuditLog.objects.filter(model_name='customers.Customer').count(),
            0,
        )

    def test_product_create_logged(self):
        cat = Category.objects.create(name='دسته', slug='cat-test')
        AuditLog.objects.all().delete()

        Product.objects.create(
            name='کالا', code='P1', category=cat, price=100000,
        )

        self.assertTrue(
            AuditLog.objects.filter(
                model_name='products.Product', action='created'
            ).exists()
        )

    def test_user_creation_logged(self):
        User.objects.create_user('test_user_new', password='t123456')
        self.assertTrue(
            AuditLog.objects.filter(
                model_name='auth.User', action='created'
            ).exists()
        )

    def test_user_captured_via_thread_local(self):
        from crm.middleware import _thread_locals
        _thread_locals.user = self.user
        try:
            Customer.objects.create(name='تست', mobile='09120000999')
            log = AuditLog.objects.filter(
                model_name='customers.Customer', action='created'
            ).first()
            self.assertEqual(log.user, self.user)
        finally:
            _thread_locals.user = None

    def test_user_display_fallback(self):
        Customer.objects.create(name='تست', mobile='09120000999')
        log = AuditLog.objects.filter(
            model_name='customers.Customer'
        ).first()
        self.assertEqual(log.user_display, 'سیستم')

    def test_action_icon(self):
        Customer.objects.create(name='تست', mobile='09120000999')
        log = AuditLog.objects.first()
        self.assertEqual(log.icon, '➕')