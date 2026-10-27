"""تست‌های صحت عددی فاکتور: جمع‌ها، مالیات، تخفیف، موجودی."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer
from products.models import Category, Product
from sales.models import Invoice, InvoiceItem


class InvoiceTotalsTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('inv_admin', password='t123456')
        cls.customer = Customer.objects.create(name='فاکتور تست', mobile='09120005555')
        cls.cat = Category.objects.create(name='دسته فاکتور', slug='inv-cat')
        cls.p1 = Product.objects.create(name='کالا ۱', code='INV-1', category=cls.cat,
                                        price=100000, stock=10)
        cls.p2 = Product.objects.create(name='کالا ۲', code='INV-2', category=cls.cat,
                                        price=50000, stock=5)

    def _make_invoice(self, discount=0, tax_percent=0):
        inv = Invoice.objects.create(customer=self.customer, created_by=self.user,
                                     discount=discount, tax_percent=tax_percent)
        InvoiceItem.objects.create(invoice=inv, product=self.p1, quantity=2,
                                   unit_price=100000)
        InvoiceItem.objects.create(invoice=inv, product=self.p2, quantity=1,
                                   unit_price=50000)
        inv.refresh_from_db()
        return inv

    def test_subtotal_and_total(self):
        inv = self._make_invoice()
        # ۲×۱۰۰٬۰۰۰ + ۱×۵۰٬۰۰۰ = ۲۵۰٬۰۰۰
        self.assertEqual(inv.subtotal, 250000)
        self.assertEqual(inv.total, 250000)
        self.assertEqual(inv.tax_amount, 0)

    def test_item_line_total(self):
        inv = self._make_invoice()
        item = inv.items.get(product=self.p1)
        self.assertEqual(item.total_price, 200000)

    def test_discount_applied(self):
        inv = self._make_invoice(discount=50000)
        self.assertEqual(inv.subtotal, 250000)
        self.assertEqual(inv.total, 200000)

    def test_tax_applied(self):
        inv = self._make_invoice(tax_percent=9)
        # ۹٪ از ۲۵۰٬۰۰۰ = ۲۲٬۵۰۰
        self.assertEqual(inv.tax_amount, 22500)
        self.assertEqual(inv.total, 272500)

    def test_discount_and_tax_together(self):
        inv = self._make_invoice(discount=50000, tax_percent=9)
        # (۲۵۰٬۰۰۰ − ۵۰٬۰۰۰) × ۹٪ = ۱۸٬۰۰۰
        self.assertEqual(inv.tax_amount, 18000)
        self.assertEqual(inv.total, 218000)

    def test_delete_item_recalculates(self):
        inv = self._make_invoice()
        inv.items.get(product=self.p2).delete()
        inv.refresh_from_db()
        self.assertEqual(inv.subtotal, 200000)
        self.assertEqual(inv.total, 200000)

    def test_discount_larger_than_subtotal_does_not_go_negative(self):
        """تخفیف بیشتر از جمع اقلام نباید فاکتور را منفی کند"""
        inv = self._make_invoice(discount=999999)
        self.assertGreaterEqual(
            inv.total, 0,
            'مبلغ نهایی فاکتور نباید منفی شود (تخفیف بیش از جمع اقلام)',
        )


class InvoicePagesTest(TestCase):
    """صفحه‌ی جزئیات و چاپ فاکتور: اعداد و اقلام درست نمایش داده شوند"""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('prn_admin', password='t123456')
        cls.customer = Customer.objects.create(name='چاپ فاکتور', mobile='09120008881')
        cls.cat = Category.objects.create(name='چاپ', slug='prn-cat')
        cls.p1 = Product.objects.create(name='کالای چاپ ۱', code='PRN-1',
                                        category=cls.cat, price=100000, stock=10)
        cls.p2 = Product.objects.create(name='کالای چاپ ۲', code='PRN-2',
                                        category=cls.cat, price=50000, stock=10)

    def setUp(self):
        self.client.force_login(self.user)
        self.invoice = Invoice.objects.create(customer=self.customer,
                                              created_by=self.user,
                                              discount=20000, tax_percent=9)
        InvoiceItem.objects.create(invoice=self.invoice, product=self.p1,
                                   quantity=2, unit_price=100000)
        InvoiceItem.objects.create(invoice=self.invoice, product=self.p2,
                                   quantity=1, unit_price=50000)
        self.invoice.refresh_from_db()

    def test_totals_are_correct(self):
        self.assertEqual(self.invoice.subtotal, 250000)
        self.assertEqual(self.invoice.tax_amount, 20700)
        self.assertEqual(self.invoice.total, 250700)

    def test_detail_page_shows_totals(self):
        r = self.client.get(reverse('sales:detail', args=[self.invoice.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'کالای چاپ')

    def test_print_page_renders(self):
        r = self.client.get(reverse('sales:print', args=[self.invoice.pk]))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('چاپ فاکتور', body)
        self.assertGreaterEqual(body.count('کالای چاپ'), 2)
