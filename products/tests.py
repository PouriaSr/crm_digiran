"""
تست‌های products — StockMovement، change_stock، و Soft Delete
"""
from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.urls import reverse

from .models import Product, StockMovement, Category
from accounts.forms import ensure_groups, ROLE_GROUP_MAP


# ═══════════════════════════════════════════════════════════
# تست Product.change_stock
# ═══════════════════════════════════════════════════════════
class ChangeStockTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('stock_user', password='t123456')
        cls.category = Category.objects.create(name='دسته تستی', slug='test-stock-cat')
        cls.product = Product.objects.create(
            name='کالای تستی', code='TEST-001', category=cls.category,
            price=100000, cost_price=80000, stock=50,
        )

    def test_increase_stock(self):
        result = self.product.change_stock(quantity=+10, movement_type='in', user=self.user)
        self.assertEqual(result, 60)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 60)
        movement = StockMovement.objects.latest('created_at')
        self.assertEqual(movement.stock_before, 50)
        self.assertEqual(movement.stock_after, 60)

    def test_cannot_go_negative(self):
        with self.assertRaises(ValueError):
            self.product.change_stock(quantity=-100, movement_type='out', user=self.user)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 50)


# ═══════════════════════════════════════════════════════════
# تست Soft Delete و Restore (View Level)
# ═══════════════════════════════════════════════════════════
class ProductSoftDeleteViewTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        ensure_groups()
        cls.admin = User.objects.create_superuser('admin_prod', password='t123456')
        
        cls.sales = User.objects.create_user('sales_prod', password='t123456')
        cls.sales.groups.add(Group.objects.get(name=ROLE_GROUP_MAP['sales']))
        
        cls.category = Category.objects.create(name='دسته تست', slug='test-del-cat')
        cls.product = Product.objects.create(name='کالای حذف شدنی', code='DEL-001', category=cls.category)

    def test_delete_product_soft_deletes(self):
        """مدیر باید بتواند کالا را حذف نرم کند"""
        self.client.force_login(self.admin)
        url = reverse('products:delete', args=[self.product.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_deleted)

    def test_sales_cannot_delete_product(self):
        """کارشناس فروش نباید بتواند کالا را حذف کند (403)"""
        self.client.force_login(self.sales)
        url = reverse('products:delete', args=[self.product.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_deleted)


# ═══════════════════════════════════════════════════════════
# تست تشخیص کد تکراری
# ═══════════════════════════════════════════════════════════
class ProductDuplicateTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='دسته اصلی', slug='main-cat')
        cls.existing = Product.objects.create(name='کالای موجود', code='EXIST-001', category=cls.category)

    def test_duplicate_code_blocks_save(self):
        from .forms import ProductForm
        form = ProductForm(data={
            'name': 'کالای جدید', 
            'code': 'EXIST-001', 
            'category': self.category.pk,
            'unit': 'عدد', 
            'price': 50000, 
            'stock': 5, 
            'is_active': True,
            'cost_price': 0,   # ⭐ اضافه شد
            'min_stock': 0,    # ⭐ اضافه شد
        })
        self.assertFalse(form.is_valid())
        self.assertIn('code', form.errors)