"""
تست‌های accounts — RBAC و permissions
"""
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User, Group, AnonymousUser
from django.http import HttpResponse
from django.urls import reverse

from .permissions import (
    get_user_role, get_user_role_display, has_role, has_permission,
    get_user_permissions, require_permission, require_roles,
    PERMISSIONS,
    ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES,
    ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_OPERATOR,
    ROLE_TO_GROUP,
)
from .forms import ROLE_GROUP_MAP, ensure_groups


# ═══════════════════════════════════════════════════════════
# تست توابع کمکی permissions.py
# ═══════════════════════════════════════════════════════════
class PermissionsHelpersTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        ensure_groups()
        cls.admin = User.objects.create_superuser('t_admin', password='t123456')
        cls.sales = User.objects.create_user('t_sales', password='t123456')
        cls.sales.groups.add(Group.objects.get(name='کارشناس فروش'))
        cls.support = User.objects.create_user('t_support', password='t123456')
        cls.support.groups.add(Group.objects.get(name='پشتیبان'))
        cls.no_role = User.objects.create_user('t_norole', password='t123456')

    # ─── get_user_role ───
    def test_get_user_role_superuser(self):
        self.assertEqual(get_user_role(self.admin), ROLE_ADMIN)

    def test_get_user_role_sales(self):
        self.assertEqual(get_user_role(self.sales), ROLE_SALES)

    def test_get_user_role_support(self):
        self.assertEqual(get_user_role(self.support), ROLE_SUPPORT)

    def test_get_user_role_none(self):
        self.assertEqual(get_user_role(self.no_role), 'none')

    def test_get_user_role_anonymous(self):
        self.assertIsNone(get_user_role(AnonymousUser()))

    def test_get_user_role_display(self):
        self.assertEqual(get_user_role_display(self.admin), 'مدیر کل')
        self.assertEqual(get_user_role_display(self.sales), 'کارشناس فروش')

    # ─── has_role ───
    def test_has_role_admin(self):
        self.assertTrue(has_role(self.admin, ROLE_ADMIN))
        self.assertTrue(has_role(self.admin, ROLE_SALES))
        self.assertTrue(has_role(self.admin, ROLE_OPERATOR))

    def test_has_role_sales(self):
        self.assertTrue(has_role(self.sales, ROLE_SALES))
        self.assertFalse(has_role(self.sales, ROLE_ADMIN))

    # ─── has_permission ───
    def test_has_permission_superuser_has_all(self):
        for perm_name in PERMISSIONS.keys():
            self.assertTrue(
                has_permission(self.admin, perm_name),
                f'admin باید {perm_name} را داشته باشد'
            )

    def test_has_permission_sales_can_view_customers(self):
        self.assertTrue(has_permission(self.sales, 'customers.view'))
        self.assertTrue(has_permission(self.sales, 'customers.add'))
        self.assertTrue(has_permission(self.sales, 'customers.edit'))

    def test_has_permission_sales_cannot_delete_customers(self):
        self.assertFalse(has_permission(self.sales, 'customers.delete'))

    def test_has_permission_support_cannot_reassign(self):
        self.assertFalse(has_permission(self.support, 'calls.reassign'))

    def test_has_permission_support_cannot_delete_calls(self):
        self.assertFalse(has_permission(self.support, 'calls.delete'))

    def test_has_permission_unknown_permission(self):
        self.assertFalse(has_permission(self.sales, 'unknown.permission'))

    def test_has_permission_anonymous(self):
        self.assertFalse(has_permission(AnonymousUser(), 'customers.view'))

    # ─── get_user_permissions ───
    def test_get_user_permissions_admin_has_all(self):
        self.assertEqual(get_user_permissions(self.admin), set(PERMISSIONS.keys()))

    def test_get_user_permissions_sales(self):
        perms = get_user_permissions(self.sales)
        self.assertIn('customers.view', perms)
        self.assertIn('customers.add', perms)
        self.assertNotIn('customers.delete', perms)
        self.assertNotIn('products.delete', perms)

    def test_get_user_permissions_support(self):
        perms = get_user_permissions(self.support)
        self.assertNotIn('calls.reassign', perms)
        self.assertNotIn('calls.delete', perms)
        self.assertNotIn('invoices.add', perms)

    def test_get_user_permissions_no_role(self):
        self.assertEqual(get_user_permissions(self.no_role), set())

    def test_get_user_permissions_anonymous(self):
        self.assertEqual(get_user_permissions(AnonymousUser()), set())


# ═══════════════════════════════════════════════════════════
# تست decoratorها — ۸.۱: پیش‌فرض جدید = 403
# ═══════════════════════════════════════════════════════════
class RequirePermissionDecoratorTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        ensure_groups()
        cls.admin = User.objects.create_superuser('d_admin', password='t123456')
        cls.sales = User.objects.create_user('d_sales', password='t123456')
        cls.sales.groups.add(Group.objects.get(name='کارشناس فروش'))

    def setUp(self):
        self.factory = RequestFactory()

    def _make_request(self, user):
        """ساخت request با messages و session شبیه‌سازی‌شده"""
        from django.contrib.messages.storage.fallback import FallbackStorage
        request = self.factory.get('/')
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_allows_authorized_user(self):
        @require_permission('customers.view')
        def my_view(request):
            return HttpResponse('ok')

        request = self._make_request(self.sales)
        response = my_view(request)
        self.assertEqual(response.status_code, 200)

    def test_blocks_unauthorized_user_with_403(self):
        """پیش‌فرض جدید: 403 (نه redirect)"""
        @require_permission('customers.delete')
        def my_view(request):
            return HttpResponse('ok')

        request = self._make_request(self.sales)
        response = my_view(request)
        self.assertEqual(response.status_code, 403)

    def test_blocks_unauthorized_user_with_redirect_option(self):
        """حالت قدیم هنوز کار می‌کنه (با on_denied='redirect')"""
        @require_permission('customers.delete', on_denied='redirect')
        def my_view(request):
            return HttpResponse('ok')

        request = self._make_request(self.sales)
        response = my_view(request)
        self.assertEqual(response.status_code, 302)

    def test_blocks_anonymous_user_redirects_to_login(self):
        """کاربر ناشناس هنوز به login می‌ره (302)"""
        @require_permission('customers.view')
        def my_view(request):
            return HttpResponse('ok')

        request = self._make_request(AnonymousUser())
        response = my_view(request)
        self.assertEqual(response.status_code, 302)

    def test_ajax_unauthorized_returns_401_json(self):
        """AJAX کاربر ناشناس → 401 JSON"""
        @require_permission('customers.view')
        def my_view(request):
            return HttpResponse('ok')

        from django.contrib.messages.storage.fallback import FallbackStorage
        request = self.factory.get('/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        request.user = AnonymousUser()
        request.session = {}
        request._messages = FallbackStorage(request)

        response = my_view(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_ajax_forbidden_returns_403_json(self):
        """AJAX کاربر بدون دسترسی → 403 JSON"""
        @require_permission('customers.delete')
        def my_view(request):
            return HttpResponse('ok')

        from django.contrib.messages.storage.fallback import FallbackStorage
        request = self.factory.get('/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        request.user = self.sales
        request.session = {}
        request._messages = FallbackStorage(request)

        response = my_view(request)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_superuser_always_allowed(self):
        @require_permission('accounts.manage_users')
        def my_view(request):
            return HttpResponse('ok')

        request = self._make_request(self.admin)
        response = my_view(request)
        self.assertEqual(response.status_code, 200)


class RequireRolesDecoratorTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        ensure_groups()
        cls.admin = User.objects.create_superuser('r_admin', password='t123456')
        cls.sales = User.objects.create_user('r_sales', password='t123456')
        cls.sales.groups.add(Group.objects.get(name='کارشناس فروش'))

    def setUp(self):
        self.factory = RequestFactory()

    def _make_request(self, user):
        """ساخت request با messages و session شبیه‌سازی‌شده"""
        from django.contrib.messages.storage.fallback import FallbackStorage
        request = self.factory.get('/')
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_allows_matching_role(self):
        @require_roles(ROLE_SALES, ROLE_ADMIN)
        def my_view(request):
            return HttpResponse('ok')

        request = self._make_request(self.sales)
        response = my_view(request)
        self.assertEqual(response.status_code, 200)

    def test_blocks_non_matching_role_with_403(self):
        """پیش‌فرض جدید: 403"""
        @require_roles(ROLE_ADMIN)
        def my_view(request):
            return HttpResponse('ok')

        request = self._make_request(self.sales)
        response = my_view(request)
        self.assertEqual(response.status_code, 403)

    def test_superuser_always_allowed(self):
        @require_roles(ROLE_SALES)
        def my_view(request):
            return HttpResponse('ok')

        request = self._make_request(self.admin)
        response = my_view(request)
        self.assertEqual(response.status_code, 200)


# ═══════════════════════════════════════════════════════════
# تست ماتریس دسترسی — سناریوهای کلیدی
# ═══════════════════════════════════════════════════════════
class RolesMatrixTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        ensure_groups()
        cls.admin = User.objects.create_superuser('m_admin', password='t123456')
        cls.sm = User.objects.create_user('m_sm', password='t123456')
        cls.sm.groups.add(Group.objects.get(name='مدیر فروش'))
        cls.sales = User.objects.create_user('m_sales', password='t123456')
        cls.sales.groups.add(Group.objects.get(name='کارشناس فروش'))
        cls.support = User.objects.create_user('m_support', password='t123456')
        cls.support.groups.add(Group.objects.get(name='پشتیبان'))
        cls.acc = User.objects.create_user('m_acc', password='t123456')
        cls.acc.groups.add(Group.objects.get(name='حسابدار'))
        cls.op = User.objects.create_user('m_op', password='t123456')
        cls.op.groups.add(Group.objects.get(name='اپراتور'))

        cls.all_non_admins = [cls.sm, cls.sales, cls.support, cls.acc, cls.op]

    def test_only_admin_can_delete_products(self):
        self.assertTrue(has_permission(self.admin, 'products.delete'))
        for u in self.all_non_admins:
            self.assertFalse(has_permission(u, 'products.delete'))

    def test_sales_manager_can_add_product(self):
        self.assertTrue(has_permission(self.sm, 'products.add'))
        self.assertTrue(has_permission(self.sm, 'products.edit'))

    def test_sales_cannot_add_product(self):
        self.assertFalse(has_permission(self.sales, 'products.add'))

    def test_only_admin_can_manage_users(self):
        self.assertTrue(has_permission(self.admin, 'accounts.manage_users'))
        for u in self.all_non_admins:
            self.assertFalse(has_permission(u, 'accounts.manage_users'))

    def test_operator_cannot_view_invoices(self):
        self.assertFalse(has_permission(self.op, 'invoices.view'))

    def test_accountant_can_delete_invoices(self):
        self.assertTrue(has_permission(self.acc, 'invoices.delete'))

    def test_sales_cannot_delete_invoices(self):
        self.assertFalse(has_permission(self.sales, 'invoices.delete'))

    def test_support_can_print_invoices(self):
        self.assertTrue(has_permission(self.support, 'invoices.print'))

    def test_support_cannot_create_invoices(self):
        self.assertFalse(has_permission(self.support, 'invoices.add'))

    def test_only_admin_can_manage_employees(self):
        self.assertTrue(has_permission(self.admin, 'hr.manage_employees'))
        self.assertFalse(has_permission(self.sm, 'hr.manage_employees'))

    def test_sm_can_view_employees(self):
        self.assertTrue(has_permission(self.sm, 'hr.view_employees'))

    def test_sales_cannot_view_employees(self):
        self.assertFalse(has_permission(self.sales, 'hr.view_employees'))

    def test_sales_can_view_tasks(self):
        self.assertTrue(has_permission(self.sales, 'hr.view_tasks'))

    def test_export_excel_allowed_roles(self):
        self.assertTrue(has_permission(self.admin, 'dashboard.export'))
        self.assertTrue(has_permission(self.sm, 'dashboard.export'))
        self.assertTrue(has_permission(self.acc, 'dashboard.export'))

    def test_export_excel_denied_roles(self):
        self.assertFalse(has_permission(self.sales, 'dashboard.export'))
        self.assertFalse(has_permission(self.support, 'dashboard.export'))
        self.assertFalse(has_permission(self.op, 'dashboard.export'))

    def test_all_roles_can_view_dashboard(self):
        for u in [self.admin, self.sm, self.sales, self.support, self.acc, self.op]:
            self.assertTrue(
                has_permission(u, 'dashboard.view'),
                f'{u.username} باید dashboard.view داشته باشد'
            )


# ═══════════════════════════════════════════════════════════
# تست RBAC روی Viewها — Integration با Client
# ═══════════════════════════════════════════════════════════
class RBACOnViewsTest(TestCase):
    """تست دسترسی واقعی روی URLها با Client — ۸.۱: انتظار 403"""

    @classmethod
    def setUpTestData(cls):
        ensure_groups()
        cls.users = {}

        cls.users[ROLE_ADMIN] = User.objects.create_superuser('v_admin', password='t123456')

        for role in [ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_OPERATOR]:
            u = User.objects.create_user(f'v_{role}', password='t123456')
            u.groups.add(Group.objects.get(name=ROLE_TO_GROUP[role]))
            cls.users[role] = u

    def _check_url(self, url_name, allowed_roles, expected_deny_status=403):
        """
        برای هر نقش، URL رو باز کن:
        - اگه توی allowed_roles باشه → باید 200 بگیره
        - اگه نباشه → باید expected_deny_status بگیره (پیش‌فرض 403)
        """
        url = reverse(url_name)
        for role, user in self.users.items():
            with self.subTest(role=role, url=url_name):
                self.client.force_login(user)
                # بعضی URLهای قدیمی به مسیر جدید ریدایرکت می‌شوند
                response = self.client.get(url, follow=True)

                if role in allowed_roles:
                    self.assertEqual(
                        response.status_code, 200,
                        f'{role} باید به {url_name} دسترسی داشته باشد، '
                        f'ولی status={response.status_code} گرفت'
                    )
                else:
                    self.assertEqual(
                        response.status_code, expected_deny_status,
                        f'{role} نباید به {url_name} دسترسی داشته باشد، '
                        f'ولی status={response.status_code} گرفت'
                    )
                self.client.logout()

    # ─── مشتریان ───
    def test_customers_list_access(self):
        self._check_url('customers:list', [
            ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES,
            ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_OPERATOR,
        ])

    def test_customers_create_access(self):
        self._check_url('customers:create', [
            ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES,
            ROLE_SUPPORT, ROLE_OPERATOR,
        ])

    # ─── محصولات ───
    def test_products_list_access(self):
        self._check_url('products:list', [
            ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES,
            ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_OPERATOR,
        ])

    def test_products_create_access(self):
        self._check_url('products:create', [
            ROLE_ADMIN, ROLE_SALES_MANAGER,
        ])

    # ─── فاکتورها ───
    def test_invoices_list_access(self):
        self._check_url('sales:list', [
            ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES,
            ROLE_SUPPORT, ROLE_ACCOUNTANT,
        ])

    def test_invoices_create_access(self):
        self._check_url('sales:create', [
            ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_ACCOUNTANT,
        ])

    # ─── تماس‌ها ───
    def test_calls_list_access(self):
        self._check_url('calls:list', [
            ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES,
            ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_OPERATOR,
        ])

    def test_calls_create_access(self):
        self._check_url('calls:create', [
            ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES,
            ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_OPERATOR,
        ])

    # ─── داشبورد ───
    def test_dashboard_access(self):
        self._check_url('dashboard:home', [
            ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES,
            ROLE_SUPPORT, ROLE_ACCOUNTANT, ROLE_OPERATOR,
        ])

    # ─── منابع انسانی ───
    def test_hr_employees_list_access(self):
        self._check_url('hr:employee_list', [
            ROLE_ADMIN, ROLE_SALES_MANAGER,
        ])

    def test_hr_tasks_list_access(self):
        # operator دسترسی default دارد (قابل override)
        self._check_url('hr:task_list', [
            ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT,
            ROLE_OPERATOR,
        ])

    def test_hr_leaves_list_is_open_for_all(self):
        """leave_list برای همه‌ی لاگین‌شده‌ها بازه"""
        url = reverse('hr:leave_list')
        for role, user in self.users.items():
            with self.subTest(role=role):
                self.client.force_login(user)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.client.logout()

    def test_hr_attendance_list_access(self):
        self._check_url('hr:attendance_list', [
            ROLE_ADMIN, ROLE_SALES_MANAGER,
        ])

    # ─── مدیریت کاربران ───
    def test_accounts_user_list_access(self):
        """همه‌ی viewهای accounts حالا با require_permission → 403"""
        self._check_url('accounts:user_list', [ROLE_ADMIN])

    # ─── کاربر ناشناس ───
    def test_anonymous_redirects_to_login(self):
        """کاربر لاگین‌نشده باید به login بره"""
        url = reverse('customers:list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    # ─── تست دسترسی مستقیم به URL ممنوع ───
    def test_operator_cannot_access_invoice_create_directly(self):
        """اپراتور با URL مستقیم هم نمی‌تونه فاکتور بسازه → 403"""
        self.client.force_login(self.users[ROLE_OPERATOR])
        response = self.client.get(reverse('sales:create'))
        self.assertEqual(response.status_code, 403)

    def test_support_cannot_access_product_create_directly(self):
        """پشتیبان نمی‌تونه کالا اضافه کنه → 403"""
        self.client.force_login(self.users[ROLE_SUPPORT])
        response = self.client.get(reverse('products:create'))
        self.assertEqual(response.status_code, 403)

    def test_sales_cannot_access_hr_employees_directly(self):
        """کارشناس فروش نمی‌تونه پرسنل رو ببینه → 403"""
        self.client.force_login(self.users[ROLE_SALES])
        response = self.client.get(reverse('hr:employee_list'))
        self.assertEqual(response.status_code, 403)

    # ─── تست محتوای صفحه‌ی 403 ───
    def test_403_page_contains_key_elements(self):
        """صفحه‌ی 403 باید عنوان، دکمه بازگشت، و نقش کاربر رو داشته باشه"""
        self.client.force_login(self.users[ROLE_OPERATOR])
        response = self.client.get(reverse('sales:create'))

        self.assertEqual(response.status_code, 403)
        content = response.content.decode('utf-8')
        self.assertIn('۴۰۳', content)
        self.assertIn('دسترسی غیرمجاز', content)
        self.assertIn('بازگشت به داشبورد', content)
        # نقش کاربر
        self.assertIn('اپراتور', content)
        

# ═══════════════════════════════════════════════════════════
# ۸.۲ — Rate Limiting روی login
# ═══════════════════════════════════════════════════════════
from django.core.cache import cache
from .ratelimit import (
    get_client_ip, is_locked, get_lock_remaining,
    register_failure, clear_failures, get_remaining_attempts,
    _key_user, _key_ip,
)


class LoginRateLimitUnitTest(TestCase):
    """تست‌های واحد روی توابع ratelimit.py"""

    def setUp(self):
        cache.clear()

    def test_get_client_ip_direct(self):
        from django.test import RequestFactory
        factory = RequestFactory()
        req = factory.get('/', REMOTE_ADDR='10.0.0.5')
        self.assertEqual(get_client_ip(req), '10.0.0.5')

    def test_get_client_ip_forwarded(self):
        from django.test import RequestFactory
        factory = RequestFactory()
        req = factory.get('/', HTTP_X_FORWARDED_FOR='203.0.113.7, 10.0.0.1')
        self.assertEqual(get_client_ip(req), '203.0.113.7')

    def test_get_client_ip_real_ip_header(self):
        from django.test import RequestFactory
        factory = RequestFactory()
        req = factory.get('/', HTTP_X_REAL_IP='203.0.113.9')
        self.assertEqual(get_client_ip(req), '203.0.113.9')

    def test_not_locked_initially(self):
        self.assertFalse(is_locked('u1', '1.1.1.1'))
        self.assertEqual(get_lock_remaining('u1', '1.1.1.1'), 0)

    def test_register_failures_below_limit(self):
        for i in range(4):
            result = register_failure('u1', '1.1.1.1')
        self.assertIsNone(result)  # هنوز قفل نشده
        self.assertFalse(is_locked('u1', '1.1.1.1'))
        self.assertEqual(get_remaining_attempts('u1', '1.1.1.1'), 1)

    def test_lock_after_user_limit(self):
        for _ in range(5):
            register_failure('u1', '1.1.1.1')
        self.assertTrue(is_locked('u1', '1.1.1.1'))
        self.assertGreater(get_lock_remaining('u1', '1.1.1.1'), 0)

    def test_clear_failures(self):
        for _ in range(3):
            register_failure('u1', '1.1.1.1')
        clear_failures('u1', '1.1.1.1')
        self.assertFalse(is_locked('u1', '1.1.1.1'))
        self.assertEqual(get_remaining_attempts('u1', '1.1.1.1'), 5)

    def test_different_ips_are_independent(self):
        for _ in range(5):
            register_failure('u1', '1.1.1.1')
        self.assertTrue(is_locked('u1', '1.1.1.1'))
        self.assertFalse(is_locked('u1', '2.2.2.2'))

    def test_ip_layer_blocks_after_many_usernames(self):
        """۲۰ تلاش از یک IP با usernameهای مختلف → IP قفل می‌شه"""
        for i in range(20):
            register_failure(f'u{i}', '1.1.1.1')
        self.assertTrue(is_locked('brandnew', '1.1.1.1'))


class LoginRateLimitViewTest(TestCase):
    """تست‌های integration روی RateLimitedLoginView"""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('rl_user', password='correct1234')
        self.url = reverse('accounts:login')

    def _fail_login(self, username='rl_user', ip='127.0.0.1'):
        return self.client.post(
            self.url,
            {'username': username, 'password': 'wrong-password'},
            REMOTE_ADDR=ip,
        )

    def _success_login(self, username='rl_user', ip='127.0.0.1'):
        return self.client.post(
            self.url,
            {'username': username, 'password': 'correct1234'},
            REMOTE_ADDR=ip,
        )

    def test_successful_login_no_lock(self):
        response = self._success_login()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(is_locked('rl_user', '127.0.0.1'))

    def test_failed_login_increments_counter(self):
        self._fail_login()
        # هنوز قفل نیست ولی یک تلاش کم شده
        self.assertFalse(is_locked('rl_user', '127.0.0.1'))
        self.assertEqual(get_remaining_attempts('rl_user', '127.0.0.1'), 4)

    def test_lockout_after_max_failed_attempts(self):
        for _ in range(5):
            self._fail_login()
        self.assertTrue(is_locked('rl_user', '127.0.0.1'))

    def test_correct_password_after_lockout_is_blocked(self):
        """حتی رمز درست هم بعد از قفل کار نمی‌کنه"""
        for _ in range(5):
            self._fail_login()

        response = self._success_login()

        # باید به login redirect بشه، نه داشبورد
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

        # کاربر نباید لاگین شده باشه
        self.assertFalse(self.client.session.get('_auth_user_id'))

    def test_successful_login_clears_failures(self):
        for _ in range(3):
            self._fail_login()

        response = self._success_login()
        self.assertEqual(response.status_code, 302)

        # شمارنده پاک شده
        self.assertEqual(get_remaining_attempts('rl_user', '127.0.0.1'), 5)

    def test_lockout_message_shown_on_login_page(self):
        """پیام خطای قفل روی صفحه‌ی login نمایش داده می‌شه"""
        # ۵ تلاش ناموفق → قفل فعال می‌شه
        for _ in range(5):
            self._fail_login()

        # تلاش ششم → بلوک می‌شه + redirect به login + پیام
        response = self.client.post(
            self.url,
            {'username': 'rl_user', 'password': 'wrong-password'},
            REMOTE_ADDR='127.0.0.1',
            follow=True,
        )
        content = response.content.decode('utf-8')
        self.assertIn('مسدود', content)

    def test_other_ip_can_still_login(self):
        """قفل یک IP روی IP دیگه اثر نداره"""
        for _ in range(5):
            self._fail_login(ip='1.1.1.1')

        # IP جدید می‌تونه لاگین کنه
        response = self._success_login(ip='2.2.2.2')
        self.assertEqual(response.status_code, 302)


# ═══════════════════════════════════════════════════════════
# تست‌های 2FA — فاز ۸.۳
# ═══════════════════════════════════════════════════════════
import time
from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken


def _generate_valid_totp(device):
    """تولید کد TOTP معتبر برای تست"""
    totp = TOTP(device.bin_key, device.step, device.t0, device.digits)
    totp.time = time.time()
    return str(totp.token()).zfill(device.digits)


class TwoFactorSetupTest(TestCase):

    def setUp(self):
        TOTPDevice.objects.all().delete()
        StaticDevice.objects.all().delete()

        self.user = User.objects.create_user('tfa_user', password='t123456')
        self.client.force_login(self.user)

    def test_setup_page_loads(self):
        from django.urls import reverse
        r = self.client.get(reverse('accounts:twofa_setup'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'QR')

    def test_setup_creates_unconfirmed_device(self):
        from django.urls import reverse
        self.client.get(reverse('accounts:twofa_setup'))
        device = TOTPDevice.objects.filter(user=self.user).first()
        self.assertIsNotNone(device)
        self.assertFalse(device.confirmed)

    def test_setup_with_valid_code_confirms_device(self):
        from django.urls import reverse
        # ایجاد device
        self.client.get(reverse('accounts:twofa_setup'))
        device = TOTPDevice.objects.get(user=self.user)
        token = _generate_valid_totp(device)

        r = self.client.post(reverse('accounts:twofa_setup'), {'code': token})

        device.refresh_from_db()
        self.assertTrue(device.confirmed)
        # redirect به recovery codes
        self.assertEqual(r.status_code, 302)
        self.assertIn('recovery', r.url)

    def test_setup_with_invalid_code_shows_error(self):
        from django.urls import reverse
        self.client.get(reverse('accounts:twofa_setup'))

        r = self.client.post(reverse('accounts:twofa_setup'), {'code': '000000'})

        # هنوز در same page
        self.assertEqual(r.status_code, 200)
        device = TOTPDevice.objects.get(user=self.user)
        self.assertFalse(device.confirmed)

    def test_recovery_codes_generated_after_setup(self):
        from django.urls import reverse
        self.client.get(reverse('accounts:twofa_setup'))
        device = TOTPDevice.objects.get(user=self.user)
        token = _generate_valid_totp(device)

        self.client.post(reverse('accounts:twofa_setup'), {'code': token})

        # ۱۰ کد بازیابی
        static_device = StaticDevice.objects.filter(user=self.user).first()
        self.assertIsNotNone(static_device)
        self.assertEqual(static_device.token_set.count(), 10)


class TwoFactorVerifyTest(TestCase):

    def setUp(self):
        TOTPDevice.objects.all().delete()
        StaticDevice.objects.all().delete()

        self.user = User.objects.create_user('tfa_verify', password='t123456')
        self.device = TOTPDevice.objects.create(
            user=self.user, name='default', confirmed=True,
        )
        self.device.refresh_from_db()

    def test_login_with_2fa_redirects_to_verify(self):
        from django.urls import reverse
        r = self.client.post(reverse('accounts:login'), {
            'username': 'tfa_verify',
            'password': 't123456',
        })
        # redirect به verify
        self.assertEqual(r.status_code, 302)
        self.assertIn('/2fa/', r.url)
        # کاربر لاگین نشده
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_verify_with_valid_totp(self):
        from django.urls import reverse
        # اول login
        self.client.post(reverse('accounts:login'), {
            'username': 'tfa_verify', 'password': 't123456',
        })
        # کد معتبر
        token = _generate_valid_totp(self.device)
        r = self.client.post(reverse('accounts:twofa_verify'), {'code': token})

        # redirect به داشبورد
        self.assertEqual(r.status_code, 302)
        # کاربر لاگین شده
        self.assertIn('_auth_user_id', self.client.session)

    def test_verify_with_invalid_totp(self):
        from django.urls import reverse
        self.client.post(reverse('accounts:login'), {
            'username': 'tfa_verify', 'password': 't123456',
        })
        r = self.client.post(reverse('accounts:twofa_verify'), {'code': '999999'})

        self.assertEqual(r.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_verify_without_login_redirects(self):
        from django.urls import reverse
        r = self.client.get(reverse('accounts:twofa_verify'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r.url)


class TwoFactorRecoveryTest(TestCase):

    def setUp(self):
        TOTPDevice.objects.all().delete()
        StaticDevice.objects.all().delete()

        self.user = User.objects.create_user('tfa_recovery', password='t123456')
        TOTPDevice.objects.create(user=self.user, name='default', confirmed=True)

        # کدهای بازیابی
        static_device = StaticDevice.objects.create(
            user=self.user, name='recovery', confirmed=True,
        )
        self.recovery_token = StaticToken.random_token()
        static_device.token_set.create(token=self.recovery_token)

    def test_verify_with_recovery_code(self):
        from django.urls import reverse
        self.client.post(reverse('accounts:login'), {
            'username': 'tfa_recovery', 'password': 't123456',
        })
        r = self.client.post(reverse('accounts:twofa_verify'), {
            'code': self.recovery_token,
        })

        # لاگین موفق
        self.assertEqual(r.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

    def test_recovery_code_consumed_after_use(self):
        from django.urls import reverse
        self.client.post(reverse('accounts:login'), {
            'username': 'tfa_recovery', 'password': 't123456',
        })
        self.client.post(reverse('accounts:twofa_verify'), {
            'code': self.recovery_token,
        })

        # کد باید مصرف شده باشه
        static_device = StaticDevice.objects.filter(user=self.user).first()
        self.assertEqual(static_device.token_set.count(), 0)

    def test_recovery_code_single_use(self):
        from django.urls import reverse
        # بار اول
        self.client.post(reverse('accounts:login'), {
            'username': 'tfa_recovery', 'password': 't123456',
        })
        self.client.post(reverse('accounts:twofa_verify'), {
            'code': self.recovery_token,
        })
        self.client.logout()

        # بار دوم — باید رد بشه
        self.client.post(reverse('accounts:login'), {
            'username': 'tfa_recovery', 'password': 't123456',
        })
        r = self.client.post(reverse('accounts:twofa_verify'), {
            'code': self.recovery_token,
        })
        self.assertEqual(r.status_code, 200)  # still on verify page
        self.assertNotIn('_auth_user_id', self.client.session)


class TwoFactorDisableTest(TestCase):

    def setUp(self):
        TOTPDevice.objects.all().delete()
        StaticDevice.objects.all().delete()

        self.user = User.objects.create_user('tfa_disable', password='t123456')
        self.device = TOTPDevice.objects.create(
            user=self.user, name='default', confirmed=True,
        )
        self.device.refresh_from_db()
        self.client.force_login(self.user)

    def test_disable_with_valid_code(self):
        from django.urls import reverse
        token = _generate_valid_totp(self.device)
        r = self.client.post(reverse('accounts:twofa_disable'), {'code': token})

        self.assertEqual(r.status_code, 302)
        self.assertEqual(TOTPDevice.objects.filter(user=self.user).count(), 0)

    def test_disable_with_invalid_code(self):
        from django.urls import reverse
        r = self.client.post(reverse('accounts:twofa_disable'), {'code': '999999'})

        self.assertEqual(r.status_code, 200)
        # device باقی‌مونده
        self.assertEqual(TOTPDevice.objects.filter(user=self.user).count(), 1)


# ═══════════════════════════════════════════════════════════
# تست Duplicate — User
# ═══════════════════════════════════════════════════════════
class UserDuplicateTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.existing = User.objects.create_user(
            'existing_user', password='t123456', email='existing@example.com',
        )

    def test_unique_username_is_valid(self):
        from .forms import UserCreateForm
        form = UserCreateForm(data={
            'username': 'brand_new_user',
            'email': 'new@example.com',
            'first_name': 'X',
            'last_name': 'Y',
            'password1': 'test1234',
            'password2': 'test1234',
            'role': 'sales',
            'is_active': True,
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_duplicate_username_blocks(self):
        from .forms import UserCreateForm
        form = UserCreateForm(data={
            'username': 'existing_user',
            'email': 'new@example.com',
            'first_name': 'X',
            'last_name': 'Y',
            'password1': 'test1234',
            'password2': 'test1234',
            'role': 'sales',
            'is_active': True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_duplicate_email_blocks(self):
        from .forms import UserCreateForm
        form = UserCreateForm(data={
            'username': 'brand_new_user',
            'email': 'existing@example.com',
            'first_name': 'X',
            'last_name': 'Y',
            'password1': 'test1234',
            'password2': 'test1234',
            'role': 'sales',
            'is_active': True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
# ═══════════════════════════════════════════════════════════
# تست یکپارچگی اعلان‌ها (Notification Integration)
# ═══════════════════════════════════════════════════════════
from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from accounts.notifications import get_notifications
from accounts.forms import ensure_groups, ROLE_GROUP_MAP
from calls.models import Call
from hr.models import Task, Employee, LeaveRequest


class NotificationIntegrationTest(TestCase):
    """تست می‌کند که اعلان‌ها با لیست‌های مقصدشان هم‌خوانی داشته باشند"""

    @classmethod
    def setUpTestData(cls):
        ensure_groups()
        cls.admin = User.objects.create_superuser('admin_notif', password='t123456')
        
        # ساخت یک پروفایل پرسنلی برای ادمین
        cls.employee = Employee.objects.create(
            user=cls.admin, first_name='تست', last_name='تست', is_active=True
        )
        
        cls.today = timezone.now().date()
        cls.yesterday = cls.today - timedelta(days=1)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_call_notification_and_link(self):
        """اعلان پیگیری: بر اساس پرچم «نیاز به پیگیری» مشتری"""
        from customers.models import Customer
        # ۱. مشتری نیازمند پیگیری
        Customer.objects.create(
            name='علی', mobile='09120000000', needs_followup=True,
            stage='potential', assigned_to=self.admin, created_by=self.admin,
        )

        # ۲. چک می‌کنیم اعلان داده شود
        notifs = get_notifications(self.admin)
        call_notif = next((n for n in notifs if 'تماس نیازمند پیگیری' in n['title']), None)
        self.assertIsNotNone(call_notif, "اعلان تماس ساخته نشد!")
        
        # ۳. اعلان باید به تب «تماس و پیگیری» مرکز مشتریان برود
        self.assertEqual(call_notif['url'], '/customers/hub/?tab=info')
        response = self.client.get(call_notif['url'], follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'مرکز مشتریان')

    def test_task_notification_and_link(self):
        """تست اعلان وظایف عقب‌افتاده و لینک آن"""
        # ۱. یک وظیفه با مهلت دیروز می‌سازیم
        task = Task.objects.create(
            title='وظیفه عقب‌افتاده', due_date=self.yesterday,
            assigned_to=self.employee, status='in_progress'
        )
        
        # ۲. چک می‌کنیم اعلان داده شود
        notifs = get_notifications(self.admin)
        task_notif = next((n for n in notifs if 'وظیفه عقب‌افتاده' in n['title']), None)
        self.assertIsNotNone(task_notif, "اعلان وظیفه ساخته نشد!")
        
        # ۳. چک می‌کنیم لینک اعلان، وظیفه را به درستی نشان دهد
        response = self.client.get(task_notif['url'])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'وظیفه عقب‌افتاده')

    def test_leave_notification_and_link(self):
        """تست اعلان مرخصی در انتظار و لینک آن"""
        # ۱. یک درخواست مرخصی در انتظار می‌سازیم
        leave = LeaveRequest.objects.create(
            employee=self.employee, start_date=self.today, end_date=self.today,
            status='pending', leave_type='annual'
        )
        
        # ۲. چک می‌کنیم اعلان داده شود
        notifs = get_notifications(self.admin)
        leave_notif = next((n for n in notifs if 'مرخصی در انتظار' in n['title']), None)
        self.assertIsNotNone(leave_notif, "اعلان مرخصی ساخته نشد!")
        
        # ۳. چک می‌کنیم لینک اعلان، مرخصی را به درستی نشان دهد
        response = self.client.get(leave_notif['url'])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'تست تست') # نام کارمند