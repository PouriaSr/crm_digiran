"""تست‌های اعتبارسنجی: مقادیر منفی نباید در هیچ فرمی پذیرفته شوند."""
from django.contrib.auth.models import User
from django.test import TestCase

from ads.forms import AdProcessForm
from ads.models import AdPlatform
from customers.models import Customer
from products.forms import ProductForm
from products.models import Category
from sales.forms import InvoiceForm, InvoiceItemForm


class NegativeValuesRejectedTest(TestCase):
    """قیمت، موجودی، تخفیف، مالیات و هزینه نباید منفی باشند"""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('val_admin', password='t123456')
        cls.cat = Category.objects.create(name='اعتبارسنجی', slug='val-cat')
        cls.customer = Customer.objects.create(name='اعتبار', mobile='09120007777')
        cls.platform = AdPlatform.objects.create(name='پلتفرم اعتبار')

    def test_product_rejects_negative_price(self):
        f = ProductForm({
            'name': 'کالای منفی', 'code': 'VAL-1', 'category': self.cat.pk,
            'price': '-1000', 'cost_price': '0', 'stock': '0', 'min_stock': '0',
            'unit': 'عدد', 'is_active': 'on', 'barcode': '', 'description': '',
        })
        self.assertFalse(f.is_valid())
        self.assertIn('price', f.errors)

    def test_product_rejects_negative_stock(self):
        f = ProductForm({
            'name': 'کالای منفی', 'code': 'VAL-2', 'category': self.cat.pk,
            'price': '1000', 'cost_price': '0', 'stock': '-5', 'min_stock': '0',
            'unit': 'عدد', 'is_active': 'on', 'barcode': '', 'description': '',
        })
        self.assertFalse(f.is_valid())
        self.assertIn('stock', f.errors)

    def test_invoice_rejects_negative_discount(self):
        f = InvoiceForm({
            'customer': self.customer.pk, 'status': 'draft', 'payment_type': 'cash',
            'discount': '-5000', 'tax_percent': '9', 'notes': '', 'due_date': '',
        })
        self.assertFalse(f.is_valid())
        self.assertIn('discount', f.errors)

    def test_invoice_rejects_tax_above_100(self):
        f = InvoiceForm({
            'customer': self.customer.pk, 'status': 'draft', 'payment_type': 'cash',
            'discount': '0', 'tax_percent': '150', 'notes': '', 'due_date': '',
        })
        self.assertFalse(f.is_valid())
        self.assertIn('tax_percent', f.errors)

    def test_ad_process_rejects_negative_cost(self):
        f = AdProcessForm({
            'platform': self.platform.pk, 'name': 'فرآیند منفی', 'default_cost': '-50',
        })
        self.assertFalse(f.is_valid())
        self.assertIn('default_cost', f.errors)
