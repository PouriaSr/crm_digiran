"""
تست‌های sales — Signal، شماره فاکتور، calculate_totals، Audit Trail و مدیریت موجودی
"""
import jdatetime
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from customers.models import Customer
from products.models import Product, Category, StockMovement
from .models import Invoice, InvoiceItem, InvoiceLog


# ═══════════════════════════════════════════════════════════
# تست‌های مدل شماره فاکتور
# ═══════════════════════════════════════════════════════════
class InvoiceNumberTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.customer = Customer.objects.create(name='مشتری', mobile='09120000001')

    def test_number_format_jalali(self):
        inv = Invoice.objects.create(customer=self.customer)
        now_j = jdatetime.datetime.now()
        expected_prefix = f"INV-{now_j.year}{now_j.month:02d}-"
        self.assertTrue(inv.number.startswith(expected_prefix))

    def test_number_is_unique(self):
        inv1 = Invoice.objects.create(customer=self.customer)
        inv2 = Invoice.objects.create(customer=self.customer)
        self.assertNotEqual(inv1.number, inv2.number)


# ═══════════════════════════════════════════════════════════
# تست Signal — calculate_totals
# ═══════════════════════════════════════════════════════════
class InvoiceTotalsSignalTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.customer = Customer.objects.create(name='مشتری', mobile='09120000002')
        cls.category = Category.objects.create(name='دسته تستی', slug='test-signal-cat')
        cls.p1 = Product.objects.create(name='کالای ۱', code='P1', category=cls.category, price=100000, stock=100)
        cls.p2 = Product.objects.create(name='کالای ۲', code='P2', category=cls.category, price=200000, stock=100)

    def test_totals_calculated_on_item_create(self):
        inv = Invoice.objects.create(customer=self.customer)
        InvoiceItem.objects.create(invoice=inv, product=self.p1, quantity=2, unit_price=100000)
        inv.refresh_from_db()
        self.assertEqual(inv.subtotal, 200000)
        self.assertEqual(inv.total, 218000)


# ═══════════════════════════════════════════════════════════
# تست یکپارچگی موجودی انبار (View Integration)
# ═══════════════════════════════════════════════════════════
class InvoiceStockIntegrationTest(TestCase):
    """تست کاهش و افزایش خودکار موجودی انبار هنگام صدور/حذف فاکتور"""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('admin_stock', password='t123456')
        cls.customer = Customer.objects.create(name='مشتری موجودی', mobile='09120000003')
        cls.category = Category.objects.create(name='دسته موجودی', slug='stock-cat')
        cls.product = Product.objects.create(
            name='کالای موجودی', code='STK-001', category=cls.category, price=50000, stock=50
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_create_invoice_deducts_stock(self):
        """صدور فاکتور با وضعیت 'صادر شده' باید موجودی را کم کند و StockMovement بسازد"""
        url = reverse('sales:create')
        data = {
            'customer': self.customer.pk,
            'status': 'issued',
            'payment_type': 'cash',
            'discount': '0',
            'tax_percent': '9',
            'issue_date': '1405/01/01',
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-product': self.product.pk,
            'items-0-quantity': '10',
            'items-0-unit_price': '50000',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 40)
        
        movement = StockMovement.objects.filter(product=self.product).first()
        self.assertIsNotNone(movement)
        self.assertEqual(movement.quantity, -10)

    def test_delete_issued_invoice_returns_stock(self):
        """حذف فاکتور صادر شده باید موجودی را برگرداند"""
        invoice = Invoice.objects.create(customer=self.customer, status='issued')
        InvoiceItem.objects.create(invoice=invoice, product=self.product, quantity=10, unit_price=50000)
        
        self.product.change_stock(-10, 'out', reference_type='invoice')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 40)

        url = reverse('sales:delete', args=[invoice.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 50)


# ═══════════════════════════════════════════════════════════
# تست Audit Trail
# ═══════════════════════════════════════════════════════════
class InvoiceLogTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.customer = Customer.objects.create(name='م', mobile='09120000100')
        cls.category = Category.objects.create(name='د', slug='log-cat')
        cls.product = Product.objects.create(name='کالای لاگ', code='LOG-1', category=cls.category, price=100000)

    def test_created_log(self):
        invoice = Invoice.objects.create(customer=self.customer)
        logs = InvoiceLog.objects.filter(invoice=invoice)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().action, InvoiceLog.ACTION_CREATED)

    def test_status_change_log(self):
        invoice = Invoice.objects.create(customer=self.customer, status='draft')
        InvoiceLog.objects.all().delete()
        invoice.status = 'issued'
        invoice.save()
        log = InvoiceLog.objects.filter(invoice=invoice, action=InvoiceLog.ACTION_STATUS).first()
        self.assertIsNotNone(log)