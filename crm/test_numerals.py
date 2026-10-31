"""Cross-system numeral handling, including native forms and legacy records."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from crm.middleware import NormalizeNumeralInputsMiddleware, PersianDigitsMiddleware
from crm.numerals import ascii_digits, normalize_input
from dashboard.templatetags.fa_numbers import fa_digits, fa_num
from products.models import Category, Product


class NumeralInputTests(SimpleTestCase):
    def normalized(self, request):
        NormalizeNumeralInputsMiddleware(lambda req: HttpResponse())(request)
        return request

    def test_mixed_digits_and_leading_zeroes(self):
        self.assertEqual(ascii_digits('۰۹1٢۳۴۵۶۷۸۹'), '09123456789')
        self.assertEqual(normalize_input('۱۴۰۵/۰۸/۰۹ ٠٩:۳۰'), '1405/08/09 09:30')

    def test_grouped_money_and_decimal_separators(self):
        for value in ('۱٬۲۳۴٫۵۰', '1,234.50', '١٬٢٣٤٫٥٠'):
            self.assertEqual(Decimal(normalize_input(value)), Decimal('1234.50'))
        self.assertEqual(normalize_input('واحد ۱۲، طبقه ۳'), 'واحد 12، طبقه 3')

    def test_repeated_filters_formsets_and_sensitive_values(self):
        request = self.normalized(RequestFactory().post('/?owner=۱۲&owner=٣', {
            'items-0-quantity': '۲', 'items-0-unit_price': '١٬۲۵۰',
            'mobile': '۰۹۱۲۳۴۵۶۷۸۹', 'password1': 'رمز۱۲Ab',
            'old_password': 'رمز٣', 'api_key': 'key۱۲', 'csrfmiddlewaretoken': '۱۲',
            'username': 'user۱۲', 'email': 'person۱۲@example.com',
            'next': '/path/?key=۱۲', 'signature': 'abc۱۲',
        }))
        self.assertEqual(request.GET.getlist('owner'), ['12', '3'])
        self.assertEqual(request.POST['items-0-quantity'], '2')
        self.assertEqual(request.POST['items-0-unit_price'], '1250')
        self.assertEqual(request.POST['mobile'], '09123456789')
        for field in ('password1', 'old_password', 'api_key', 'csrfmiddlewaretoken',
                      'username', 'email', 'next', 'signature'):
            self.assertTrue(any(c in request.POST[field] for c in '۱۲٣'), field)

    def test_uploaded_bytes_and_json_body_are_unchanged(self):
        request = self.normalized(RequestFactory().post('/', {
            'count': '۱۲', 'file': SimpleUploadedFile('data12.txt', '۱۲'.encode()),
        }))
        self.assertEqual(request.POST['count'], '12')
        self.assertEqual(request.FILES['file'].read(), '۱۲'.encode())
        request = RequestFactory().post('/', '{"token":"۱۲"}', content_type='application/json')
        self.normalized(request)
        self.assertEqual(request.body, '{"token":"۱۲"}'.encode())

    def test_visible_digits_are_persian_without_corrupting_html_or_code(self):
        body = '<p>12 ١٢ &lt;img onerror=x&gt;</p><input value="0012"><script>let x=12;</script><code>key12</code>'
        response = PersianDigitsMiddleware(lambda req: HttpResponse(body))(RequestFactory().get('/'))
        rendered = response.content.decode()
        self.assertIn('۱۲ ۱۲ &lt;img onerror=x&gt;', rendered)
        for untouched in ('value="0012"', 'let x=12;', '<code>key12</code>'):
            self.assertIn(untouched, rendered)
        self.assertNotIn('<img onerror', rendered)
        self.assertEqual(fa_digits('١٢3'), '۱۲۳')
        self.assertEqual(fa_num('۱٬۲۳۴٫۵۰'), '۱,۲۳۴.۵۰')


class NumeralBusinessFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('number_admin', password='test-only-password')
        cls.category = Category.objects.create(name='دسته تست', slug='digits')
        cls.legacy = Product.objects.create(name='مدل ۱2٣', code='LEGACY۱۲٣', category=cls.category)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_persian_form_money_and_stock_save_as_numbers(self):
        result = self.client.post(reverse('products:create'), {
            'name': 'کالای جدید', 'code': 'NEW۱۲٣', 'category': str(self.category.pk),
            'unit': 'عدد', 'price': '۱٬۲۵۰٬۰۰۰', 'cost_price': '٩٠٠٠٠٠',
            'stock': '۱۲', 'min_stock': '۲', 'is_active': 'on',
        })
        self.assertEqual(result.status_code, 302)
        product = Product.objects.get(code='new123')
        self.assertEqual(product.price, Decimal('1250000'))
        self.assertEqual(product.stock, 12)

    def test_search_matches_legacy_mixed_scripts_with_any_input_script(self):
        for query in ('123', '۱۲۳', '١٢٣', '۱2٣'):
            response = self.client.get(reverse('products:list'), {'q': query})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(list(response.context['page_obj']), [self.legacy])
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.code, 'LEGACY۱۲٣')

    def test_search_keeps_literal_wildcards_and_access_checks(self):
        response = self.client.get(reverse('products:list'), {'q': '۱۲%'})
        self.assertEqual(list(response.context['page_obj']), [])
        self.client.logout()
        response = self.client.get(reverse('products:list'), {'q': '۱۲۳'})
        self.assertEqual(response.status_code, 302)
