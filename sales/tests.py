"""
تست‌های sales — Signal، شماره فاکتور شمسی، calculate_totals
"""
import jdatetime
from django.test import TestCase
from django.contrib.auth.models import User

from customers.models import Customer
from products.models import Product
from .models import Invoice, InvoiceItem


# ═══════════════════════════════════════════════════════════
# تست شماره فاکتور شمسی
# ═══════════════════════════════════════════════════════════
class InvoiceNumberTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.customer = Customer.objects.create(
            name='مشتری', mobile='09120000001',
        )

    def test_number_format_jalali(self):
        """شماره فاکتور با سال/ماه شمسی"""
        inv = Invoice.objects.create(customer=self.customer)
        now_j = jdatetime.datetime.now()
        expected_prefix = f"INV-{now_j.year}{now_j.month:02d}-"
        self.assertTrue(
            inv.number.startswith(expected_prefix),
            f'شماره {inv.number} باید با {expected_prefix} شروع شود'
        )

    def test_number_is_unique(self):
        """دو فاکتور پشت‌سرهم شماره‌های متفاوت دارن"""
        inv1 = Invoice.objects.create(customer=self.customer)
        inv2 = Invoice.objects.create(customer=self.customer)
        self.assertNotEqual(inv1.number, inv2.number)

    def test_number_has_4_digit_suffix(self):
        """پسوند ۴ رقمی"""
        inv = Invoice.objects.create(customer=self.customer)
        suffix = inv.number.split('-')[-1]
        self.assertEqual(len(suffix), 4)
        self.assertTrue(suffix.isdigit())

    def test_manual_number_preserved(self):
        """اگر شماره دستی داده بشه، تغییر نمی‌کنه"""
        inv = Invoice.objects.create(
            customer=self.customer,
            number='CUSTOM-001',
        )
        self.assertEqual(inv.number, 'CUSTOM-001')


# ═══════════════════════════════════════════════════════════
# تست Signal — calculate_totals
# ═══════════════════════════════════════════════════════════
class InvoiceTotalsSignalTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('sales_user', password='t123456')
        cls.customer = Customer.objects.create(
            name='مشتری', mobile='09120000002',
        )
        cls.p1 = Product.objects.create(
            name='کالای ۱', code='P1', price=100000, stock=100,
        )
        cls.p2 = Product.objects.create(
            name='کالای ۲', code='P2', price=200000, stock=100,
        )

    def _make_invoice(self, tax_percent=9, discount=0):
        inv = Invoice.objects.create(
            customer=self.customer,
            tax_percent=tax_percent,
            discount=discount,
        )
        return inv

    def test_totals_calculated_on_item_create(self):
        """هنگام ایجاد InvoiceItem، مبالغ خودکار محاسبه می‌شن"""
        inv = self._make_invoice()
        InvoiceItem.objects.create(
            invoice=inv, product=self.p1, quantity=2, unit_price=100000,
        )
        inv.refresh_from_db()
        self.assertEqual(inv.subtotal, 200000)
        self.assertEqual(inv.tax_amount, 18000)  # ۹٪
        self.assertEqual(inv.total, 218000)

    def test_totals_with_multiple_items(self):
        """چند قلم"""
        inv = self._make_invoice()
        InvoiceItem.objects.create(invoice=inv, product=self.p1, quantity=2, unit_price=100000)
        InvoiceItem.objects.create(invoice=inv, product=self.p2, quantity=1, unit_price=200000)
        inv.refresh_from_db()
        # ۲×۱۰۰k + ۱×۲۰۰k = ۴۰۰k
        self.assertEqual(inv.subtotal, 400000)
        self.assertEqual(inv.tax_amount, 36000)
        self.assertEqual(inv.total, 436000)

    def test_totals_with_discount(self):
        """با تخفیف"""
        inv = self._make_invoice(discount=50000)
        InvoiceItem.objects.create(invoice=inv, product=self.p1, quantity=2, unit_price=100000)
        inv.refresh_from_db()
        # ۲۰۰k - ۵۰k = ۱۵۰k → مالیات ۱۳.۵k → کل ۱۶۳.۵k
        self.assertEqual(inv.subtotal, 200000)
        self.assertEqual(inv.tax_amount, 13500)
        self.assertEqual(inv.total, 163500)

    def test_totals_recalculated_on_item_update(self):
        """ویرایش قلم → محاسبه‌ی مجدد"""
        inv = self._make_invoice()
        item = InvoiceItem.objects.create(
            invoice=inv, product=self.p1, quantity=2, unit_price=100000,
        )
        inv.refresh_from_db()
        self.assertEqual(inv.subtotal, 200000)

        # تغییر تعداد
        item.quantity = 5
        item.save()
        inv.refresh_from_db()
        self.assertEqual(inv.subtotal, 500000)

    def test_totals_recalculated_on_item_delete(self):
        """حذف قلم → محاسبه‌ی مجدد"""
        inv = self._make_invoice()
        InvoiceItem.objects.create(invoice=inv, product=self.p1, quantity=2, unit_price=100000)
        item2 = InvoiceItem.objects.create(invoice=inv, product=self.p2, quantity=1, unit_price=200000)
        inv.refresh_from_db()
        self.assertEqual(inv.subtotal, 400000)

        # حذف قلم دوم
        item2.delete()
        inv.refresh_from_db()
        self.assertEqual(inv.subtotal, 200000)
        self.assertEqual(inv.total, 218000)

    def test_totals_with_zero_items(self):
        """فاکتور بدون قلم → همه صفر"""
        inv = self._make_invoice()
        inv.refresh_from_db()
        self.assertEqual(inv.subtotal, 0)
        self.assertEqual(inv.tax_amount, 0)
        self.assertEqual(inv.total, 0)

    def test_totals_with_zero_tax(self):
        """مالیات صفر"""
        inv = self._make_invoice(tax_percent=0)
        InvoiceItem.objects.create(invoice=inv, product=self.p1, quantity=1, unit_price=100000)
        inv.refresh_from_db()
        self.assertEqual(inv.subtotal, 100000)
        self.assertEqual(inv.tax_amount, 0)
        self.assertEqual(inv.total, 100000)

    def test_tax_rounding(self):
        """رند کردن مالیات — int() استفاده می‌شه نه round()"""
        inv = self._make_invoice()
        # ۹٪ از ۱۰۰,۰۰۱ = ۹,۰۰۰.۰۹ → int = ۹,۰۰۰
        InvoiceItem.objects.create(invoice=inv, product=self.p1, quantity=1, unit_price=100001)
        inv.refresh_from_db()
        self.assertEqual(inv.tax_amount, 9000)


# ═══════════════════════════════════════════════════════════
# تست InvoiceItem.save
# ═══════════════════════════════════════════════════════════
class InvoiceItemSaveTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.customer = Customer.objects.create(name='م', mobile='09120000003')
        cls.product = Product.objects.create(
            name='کالا', code='PX', price=75000, stock=100,
        )

    def test_total_price_computed(self):
        """total_price = quantity × unit_price"""
        inv = Invoice.objects.create(customer=self.customer)
        item = InvoiceItem.objects.create(
            invoice=inv, product=self.product,
            quantity=3, unit_price=50000,
        )
        self.assertEqual(item.total_price, 150000)

    def test_unit_price_defaults_to_product_price(self):
        """اگر unit_price صفر باشه، از Product.price می‌گیره"""
        inv = Invoice.objects.create(customer=self.customer)
        item = InvoiceItem.objects.create(
            invoice=inv, product=self.product,
            quantity=2, unit_price=0,
        )
        self.assertEqual(item.unit_price, 75000)
        self.assertEqual(item.total_price, 150000)


# ═══════════════════════════════════════════════════════════
# تست calculate_totals دستی
# ═══════════════════════════════════════════════════════════
class CalculateTotalsMethodTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.customer = Customer.objects.create(name='م', mobile='09120000004')
        cls.product = Product.objects.create(
            name='کالا', code='PY', price=100000, stock=100,
        )

    def test_calculate_totals_returns_total(self):
        """calculate_totals مقدار total رو برمی‌گردونه"""
        inv = Invoice.objects.create(customer=self.customer)
        InvoiceItem.objects.create(invoice=inv, product=self.product, quantity=1, unit_price=100000)
        result = inv.calculate_totals()
        self.assertEqual(result, 109000)  # ۱۰۰k + ۹٪

    def test_calculate_totals_handles_empty(self):
        """فاکتور خالی → صفر"""
        inv = Invoice.objects.create(customer=self.customer)
        result = inv.calculate_totals()
        self.assertEqual(result, 0)


# ═══════════════════════════════════════════════════════════
# تست properties
# ═══════════════════════════════════════════════════════════
class InvoicePropertiesTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.customer = Customer.objects.create(name='م', mobile='09120000005')

    def test_status_color(self):
        inv = Invoice.objects.create(customer=self.customer, status='draft')
        self.assertEqual(inv.status_color, 'gray')
        inv.status = 'issued'
        self.assertEqual(inv.status_color, 'blue')
        inv.status = 'paid'
        self.assertEqual(inv.status_color, 'green')
        inv.status = 'cancelled'
        self.assertEqual(inv.status_color, 'red')

    def test_items_count(self):
        inv = Invoice.objects.create(customer=self.customer)
        self.assertEqual(inv.items_count, 0)

        p = Product.objects.create(name='X', code='X1', price=1000, stock=10)
        InvoiceItem.objects.create(invoice=inv, product=p, quantity=1, unit_price=1000)
        InvoiceItem.objects.create(invoice=inv, product=p, quantity=1, unit_price=1000)
        self.assertEqual(inv.items_count, 2)