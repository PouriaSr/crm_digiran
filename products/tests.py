"""
تست‌های products — StockMovement و change_stock
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.db import transaction

from .models import Product, StockMovement, Category


# ═══════════════════════════════════════════════════════════
# تست Product.change_stock
# ═══════════════════════════════════════════════════════════
class ChangeStockTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('stock_user', password='t123456')
        cls.category = Category.objects.create(
            name='دسته تستی', slug='test-stock-cat',
        )
        cls.product = Product.objects.create(
            name='کالای تستی',
            code='TEST-001',
            category=cls.category,
            price=100000,
            cost_price=80000,
            stock=50,
        )

    def test_increase_stock(self):
        """افزایش موجودی و ثبت لاگ"""
        result = self.product.change_stock(
            quantity=+10,
            movement_type='in',
            user=self.user,
            reference_type='purchase',
            reference_note='خرید',
        )
        self.assertEqual(result, 60)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 60)

        movement = StockMovement.objects.latest('created_at')
        self.assertEqual(movement.movement_type, 'in')
        self.assertEqual(movement.quantity, 10)
        self.assertEqual(movement.stock_before, 50)
        self.assertEqual(movement.stock_after, 60)
        self.assertEqual(movement.created_by, self.user)

    def test_decrease_stock(self):
        """کاهش موجودی"""
        result = self.product.change_stock(
            quantity=-5,
            movement_type='out',
            user=self.user,
        )
        self.assertEqual(result, 45)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 45)

    def test_cannot_go_negative(self):
        """اگر موجودی کافی نباشد ValueError می‌دهد"""
        with self.assertRaises(ValueError) as ctx:
            self.product.change_stock(
                quantity=-100,
                movement_type='out',
                user=self.user,
            )
        self.assertIn('کافی نیست', str(ctx.exception))

        # موجودی تغییر نکرده
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 50)

        # هیچ لاگی ثبت نشده
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_exact_zero_allowed(self):
        """صفر شدن مجاز است"""
        result = self.product.change_stock(
            quantity=-50,
            movement_type='out',
            user=self.user,
        )
        self.assertEqual(result, 0)

    def test_quantity_must_be_int(self):
        """quantity باید int باشد"""
        with self.assertRaises(ValueError):
            self.product.change_stock(
                quantity=1.5,
                movement_type='in',
                user=self.user,
            )
        with self.assertRaises(ValueError):
            self.product.change_stock(
                quantity='10',
                movement_type='in',
                user=self.user,
            )

    def test_multiple_movements_have_correct_chain(self):
        """زنجیره‌ی درست before/after"""
        self.product.change_stock(+20, 'in', user=self.user)
        self.product.change_stock(-5, 'out', user=self.user)
        self.product.change_stock(+10, 'in', user=self.user)

        movements = list(StockMovement.objects.order_by('created_at'))
        self.assertEqual(len(movements), 3)

        self.assertEqual(movements[0].stock_before, 50)
        self.assertEqual(movements[0].stock_after, 70)

        self.assertEqual(movements[1].stock_before, 70)
        self.assertEqual(movements[1].stock_after, 65)

        self.assertEqual(movements[2].stock_before, 65)
        self.assertEqual(movements[2].stock_after, 75)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 75)

    def test_optional_fields(self):
        """فیلدهای اختیاری None می‌مونن اگر پاس نشن"""
        self.product.change_stock(+5, 'in')
        movement = StockMovement.objects.latest('created_at')
        self.assertIsNone(movement.created_by)
        self.assertIsNone(movement.reference_id)
        self.assertIsNone(movement.reference_note)
        self.assertEqual(movement.reference_type, 'manual')

    def test_self_stock_updated(self):
        """بعد از change_stock، self.stock هم آپدیت شده"""
        self.product.change_stock(+10, 'in', user=self.user)
        self.assertEqual(self.product.stock, 60)


# ═══════════════════════════════════════════════════════════
# تست StockMovement model
# ═══════════════════════════════════════════════════════════
class StockMovementModelTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name='دسته تستی ۲', slug='test-sm-cat',
        )
        cls.product = Product.objects.create(
            name='کالا',
            code='SM-001',
            category=cls.category,
            price=50000,
            stock=100,
        )

    def test_is_increase_property(self):
        m1 = StockMovement.objects.create(
            product=self.product,
            movement_type='in',
            quantity=10,
            stock_before=90,
            stock_after=100,
        )
        self.assertTrue(m1.is_increase)
        self.assertEqual(m1.quantity_display, '+10')

        m2 = StockMovement.objects.create(
            product=self.product,
            movement_type='out',
            quantity=-5,
            stock_before=100,
            stock_after=95,
        )
        self.assertFalse(m2.is_increase)
        self.assertEqual(m2.quantity_display, '-5')

    def test_str_representation(self):
        m = StockMovement.objects.create(
            product=self.product,
            movement_type='out',
            quantity=-3,
            stock_before=100,
            stock_after=97,
        )
        s = str(m)
        self.assertIn('SM-001', s)
        self.assertIn('-3', s)


# ═══════════════════════════════════════════════════════════
# تست properties محصول
# ═══════════════════════════════════════════════════════════
class ProductPropertiesTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name='دسته تستی ۳', slug='test-props-cat',
        )

    def test_stock_status_out(self):
        p = Product.objects.create(
            name='A', code='A1', category=self.category,
            stock=0, min_stock=5,
        )
        self.assertEqual(p.stock_status, 'out')

    def test_stock_status_low(self):
        p = Product.objects.create(
            name='B', code='B1', category=self.category,
            stock=3, min_stock=5,
        )
        self.assertEqual(p.stock_status, 'low')
        self.assertTrue(p.is_low_stock)

    def test_stock_status_ok(self):
        p = Product.objects.create(
            name='C', code='C1', category=self.category,
            stock=10, min_stock=5,
        )
        self.assertEqual(p.stock_status, 'ok')
        self.assertFalse(p.is_low_stock)

    def test_profit_margin(self):
        p = Product.objects.create(
            name='D', code='D1', category=self.category,
            price=100000, cost_price=80000,
        )
        self.assertEqual(p.profit_margin, 25.0)

    def test_profit_margin_zero_cost(self):
        p = Product.objects.create(
            name='E', code='E1', category=self.category,
            price=100000, cost_price=0,
        )
        self.assertEqual(p.profit_margin, 0)


# ═══════════════════════════════════════════════════════════
# تست Duplicate — Product و Category
# ═══════════════════════════════════════════════════════════
class ProductDuplicateTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name='دسته اصلی', slug='main-cat',
        )
        cls.existing = Product.objects.create(
            name='کالای موجود', code='EXIST-001',
            category=cls.category, price=100000, stock=10,
        )

    def test_unique_code_is_valid(self):
        from .forms import ProductForm
        form = ProductForm(data={
            'name': 'کالای جدید',
            'code': 'NEW-001',
            'category': self.category.pk,
            'unit': 'عدد',
            'price': 50000,
            'cost_price': 40000,
            'stock': 5,
            'min_stock': 1,
            'is_active': True,
        })
        self.assertTrue(form.is_valid(), form.errors)

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
        })
        self.assertFalse(form.is_valid())
        self.assertIn('code', form.errors)
        self.assertIn('کالای موجود', str(form.errors['code']))

    def test_code_normalization_persian_digits(self):
        """کد با ارقام فارسی → نرمال‌سازی و تشخیص duplicate"""
        from .forms import ProductForm
        form = ProductForm(data={
            'name': 'X',
            'code': 'EXIST-۰۰۱',   # ارقام فارسی
            'category': self.category.pk,
            'unit': 'عدد',
            'price': 1000,
            'stock': 0,
            'is_active': True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('code', form.errors)

    def test_code_normalization_spaces(self):
        """کد با فاصله → نرمال‌سازی"""
        from .forms import ProductForm
        form = ProductForm(data={
            'name': 'X',
            'code': 'EXIST - 001',
            'category': self.category.pk,
            'unit': 'عدد',
            'price': 1000,
            'stock': 0,
            'is_active': True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('code', form.errors)

    def test_similar_name_shows_warning(self):
        """نام کاملاً مشابه → warning نه block (چون code یکتاست)"""
        from .forms import ProductForm
        form = ProductForm(data={
            'name': 'کالای موجود',   # exact same name
            'code': 'DIFFERENT-001',
            'category': self.category.pk,
            'unit': 'عدد',
            'price': 1000,
            'cost_price': 500,
            'stock': 0,
            'min_stock': 0,
            'is_active': True,
        })
        # باید valid باشه (code یکتاست)
        self.assertTrue(form.is_valid(), form.errors)
        # ولی warning برای نام
        name_warnings = [w for w in form.duplicate_warnings if w['field'] == 'name']
        self.assertGreaterEqual(len(name_warnings), 1)

    def test_edit_self_keeps_code(self):
        """ویرایش خود کالا → block نکنه"""
        from .forms import ProductForm
        form = ProductForm(
            data={
                'name': 'کالای موجود ویرایش',
                'code': 'EXIST-001',
                'category': self.category.pk,
                'unit': 'عدد',
                'price': 200000,
                'cost_price': 150000,
                'stock': 10,
                'min_stock': 2,
                'is_active': True,
            },
            instance=self.existing,
        )
        self.assertTrue(form.is_valid(), form.errors)


class CategoryDuplicateTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.existing = Category.objects.create(
            name='دسته اصلی', slug='main-cat-2',
        )

    def test_unique_name_is_valid(self):
        from .forms import CategoryForm
        form = CategoryForm(data={
            'name': 'دسته جدید',
            'slug': 'new-cat',
            'order': 1,
            'is_active': True,
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_duplicate_name_blocks(self):
        from .forms import CategoryForm
        form = CategoryForm(data={
            'name': 'دسته اصلی',
            'slug': 'another-slug',
            'order': 1,
            'is_active': True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)