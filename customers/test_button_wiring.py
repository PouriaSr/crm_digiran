"""تست ماندگار: سیم‌کشی دکمه «ثبت تماس جدید» و توابع باز کردن مودال."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer


class NewCallButtonWiringTest(TestCase):
    """دکمه باید مستقیماً تابع سراسری را صدا بزند (نه وابسته به رویداد/Alpine expression)"""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('wire_admin', password='t123456')
        cls.customer = Customer.objects.create(name='مشتری سیم‌کشی', mobile='09121237001',
                                               assigned_to=cls.user, created_by=cls.user)

    def setUp(self):
        self.client.force_login(self.user)
        self.body = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')

    def test_button_calls_global_function(self):
        self.assertIn('id="btn-new-call"', self.body)
        self.assertIn('onclick="openNewCallFromSearch()"', self.body)

    def test_global_functions_exist(self):
        self.assertIn('function openNewCallFromSearch()', self.body)
        self.assertIn('function openNewCall(detail)', self.body)
        self.assertIn('function normalizeDigitsFa(s)', self.body)

    def test_modal_root_has_id(self):
        self.assertIn('id="call-modal-root"', self.body)

    def test_modal_widget_defined(self):
        self.assertIn('function callModalWidget()', self.body)
        self.assertIn('x-data="callModalWidget()"', self.body)

    def test_open_call_sets_state(self):
        """openCall باید state را قبل از any پیش‌پر کردن ست کند"""
        self.assertIn('this.isCallModalOpen = true;', self.body)
        self.assertIn('this.mobile = d.mobile', self.body)

    def test_button_disabled_binding_kept(self):
        self.assertIn(':disabled="!showNewBtn"', self.body)


class CallModalPrefillTest(TestCase):
    """شماره/نام از جستجو باید در فیلد خودش پیش‌پر و قابل ویرایش باشد"""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('prefill_admin', password='t123456')

    def setUp(self):
        self.client.force_login(self.user)
        self.body = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')

    def test_prefill_sets_fields(self):
        self.assertIn('var wantMobile = d.mobile || \'\';', self.body)
        self.assertIn('var wantName = d.name || \'\';', self.body)
        self.assertIn('m.value = wantMobile;', self.body)
        self.assertIn('n.value = wantName;', self.body)

    def test_prefill_is_resilient(self):
        """سه پاس: فوری + بعد از رندر + تأخیری، با گارد ترتیبی"""
        self.assertIn('fill(true);                 // فوری', self.body)
        self.assertIn('this._openSeq = (this._openSeq || 0) + 1;', self.body)
        self.assertIn('if (seq !== self._openSeq) return;', self.body)

    def test_prefill_does_not_overwrite_user_input(self):
        self.assertIn('if (force || !m.value) m.value = wantMobile;', self.body)

    def test_fields_editable_by_default(self):
        # قفل فقط وقتی مشتری ثابت است (lock)
        self.assertIn('m.readOnly = !!d.lock;', self.body)
        # A missing name must remain editable because it is now required.
        self.assertIn('n.readOnly = !!d.lock && !!wantName && !/\p{N}/u.test(wantName);', self.body)

    def test_search_flow_is_unlocked(self):
        self.assertIn('var detail = { lock: false };', self.body)

    def test_row_flow_is_locked(self):
        self.assertIn("lock: true", self.body)

    def test_focus_moves_to_empty_field(self):
        self.assertIn('if (m && !m.value) {', self.body)

    def test_mobile_to_mobile_field(self):
        self.assertIn('detail.mobile = digits;', self.body)

    def test_name_to_name_field(self):
        self.assertIn('detail.name = raw;', self.body)


class SearchInputSelectorTest(TestCase):
    """در صفحه دو input[name=q] هست (هدر + مرکز مشتریان)؛ باید دومی خوانده شود"""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('sel_admin', password='t123456')

    def setUp(self):
        self.client.force_login(self.user)
        self.body = self.client.get(reverse('customers:hub') + '?tab=info').content.decode('utf-8')

    def test_hub_search_has_unique_id(self):
        self.assertIn('id="hub-search-input"', self.body)

    def test_function_targets_hub_input(self):
        self.assertIn("document.getElementById('hub-search-input')", self.body)

    def test_header_search_still_exists(self):
        # جستجوی سراسری هدر باید سر جایش بماند
        self.assertIn('action="/search/"', self.body)
