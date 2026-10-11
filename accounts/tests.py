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

    def test_has_permission_support_can_reassign(self):
        self.assertTrue(has_permission(self.support, 'calls.reassign'))

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
        self.assertIn('calls.reassign', perms)
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
                response = self.client.get(url)

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
            ROLE_SUPPORT, ROLE_OPERATOR,
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
        self._check_url('hr:task_list', [
            ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT,
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
        self.assertIn('403', content)
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