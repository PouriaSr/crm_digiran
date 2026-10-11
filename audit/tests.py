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


# ═══════════════════════════════════════════════════════════
# تست فیلترها و ویو Audit Log
# ═══════════════════════════════════════════════════════════
class AuditLogFilterTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('audit_admin', password='t123456')
        cls.user2 = User.objects.create_user('audit_user2', password='t123456')

    def setUp(self):
        AuditLog.objects.all().delete()
        self.client.force_login(self.admin)

        # ساخت داده‌های تست
        c1 = Customer.objects.create(name='مشتری ۱', mobile='09120001001')
        AuditLog.objects.all().delete()

        from crm.middleware import _thread_locals
        _thread_locals.user = self.admin
        try:
            c1.name = 'مشتری ۱ ویرایش'
            c1.save()
        finally:
            _thread_locals.user = None

        c2 = Customer.objects.create(name='مشتری ۲', mobile='09120001002')
        AuditLog.objects.filter(
            model_name='customers.Customer', object_id=c2.pk, action='created'
        ).update(user=self.user2)

    def _url(self, **params):
        from django.urls import reverse
        base = reverse('audit:list')
        if params:
            qs = '&'.join(f'{k}={v}' for k, v in params.items())
            return f'{base}?{qs}'
        return base

    def test_view_accessible_by_admin(self):
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'لاگ سیستم')

    def test_view_denied_for_non_admin(self):
        self.client.force_login(self.user2)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 403)

    def test_filter_by_action(self):
        r = self.client.get(self._url(action='updated'))
        self.assertEqual(r.status_code, 200)
        logs = list(r.context['page_obj'])
        self.assertTrue(all(log.action == 'updated' for log in logs))

    def test_filter_by_model(self):
        r = self.client.get(self._url(model='customers.Customer'))
        self.assertEqual(r.status_code, 200)
        logs = list(r.context['page_obj'])
        self.assertTrue(all(log.model_name == 'customers.Customer' for log in logs))

    def test_filter_by_user(self):
        r = self.client.get(self._url(user=self.user2.pk))
        self.assertEqual(r.status_code, 200)
        logs = list(r.context['page_obj'])
        self.assertTrue(all(log.user_id == self.user2.pk for log in logs))

    def test_filter_by_search(self):
        r = self.client.get(self._url(q='مشتری'))
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.context['page_obj']), 0)

    def test_stats_count(self):
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 200)
        stats = r.context['stats']
        self.assertIn('total', stats)
        self.assertIn('created', stats)
        self.assertIn('updated', stats)
        self.assertIn('deleted', stats)
        self.assertGreaterEqual(stats['total'], 2)

    def test_pagination_works(self):
        # ساخت ۶۰ رکورد
        for i in range(60):
            Customer.objects.create(name=f'م{i}', mobile=f'09120001{i:03d}')
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context['page_obj']), 50)  # page_size=50

    def test_filtered_count_displayed(self):
        r = self.client.get(self._url(action='updated'))
        self.assertIn('filtered_count', r.context)

    def test_empty_result_when_no_match(self):
        r = self.client.get(self._url(q='XYZ_NONEXISTENT_XYZ'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(list(r.context['page_obj'])), 0)