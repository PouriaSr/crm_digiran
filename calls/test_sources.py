from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from ads.models import Ad, AdPlatform, AdProcess, AdSource
from calls.forms import CallForm
from calls.models import Call
from customers.models import Customer


class RecordedSourceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('source_admin', password='test-only')
        cls.source = AdSource.objects.create(phone_number='09121111111', label='برچسب قدیمی')
        cls.other = AdSource.objects.create(phone_number='09122222222', label='منبع دوم')
        cls.customer = Customer.objects.create(name='آزمایش منبع', mobile='09123333333', ad_source=cls.source, assigned_to=cls.admin)
        cls.call = Call.objects.create(customer=cls.customer, caller_name=cls.customer.name, call_number=cls.customer.mobile, source=cls.source, called_by=cls.admin)
        cls.platform = AdPlatform.objects.create(name='بستر تست')
        cls.process = AdProcess.objects.create(platform=cls.platform, name='آگهی تست', default_cost=100)
        cls.ad = Ad.objects.create(platform=cls.platform, process=cls.process, source=cls.source, cost=100, ad_number='OLD', created_by=cls.admin)

    def setUp(self):
        self.client.force_login(self.admin)

    def rename(self):
        response = self.client.post(reverse('ads:source_edit', args=[self.source.pk]), {
            'phone_number': '۰۹۱۲۴۴۴۴۴۴۴', 'label': 'برچسب جدید', 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.source.refresh_from_db()

    def test_rename_and_number_change_preserve_all_recorded_sources(self):
        self.rename()
        for record in (self.call, self.ad, self.customer):
            record.refresh_from_db()
            self.assertEqual(record.source_display, '09121111111 (برچسب قدیمی)')
            record.save()  # Editing unrelated details must not refresh the source.
            record.refresh_from_db()
            self.assertEqual(record.source_label_snapshot, 'برچسب قدیمی')
        new = Call.objects.create(source=self.source, caller_name='جدید', call_number='09125555555')
        self.assertEqual(new.source_display, '09124444444 (برچسب جدید)')

    def test_each_call_keeps_its_own_selected_source(self):
        response = self.client.post(reverse('customers:hub_submit_call'), {
            'mobile': self.customer.mobile, 'name': self.customer.name, 'call_type': 'incoming',
            'purpose': 'sale', 'call_status': 'answered', 'customer_analysis': 'lead',
            'requested_condition': 'cash', 'source': self.other.pk, 'notes': 'تماس با منبع متفاوت',
        })
        self.assertEqual(response.status_code, 302)
        new = Call.objects.latest('pk')
        self.assertEqual(new.source_id, self.other.pk)
        self.assertEqual(new.source_label_snapshot, 'منبع دوم')
        self.call.refresh_from_db()
        self.assertEqual(self.call.source_label_snapshot, 'برچسب قدیمی')

    def test_quick_new_and_followup_both_require_active_source(self):
        url = reverse('customers:quick_call', args=[self.customer.pk])
        for kind in ('new', 'followup'):
            count = Call.objects.count()
            data = {'kind': kind, 'notes': 'گزارش تماس', 'follow_up_date': '1405/08/09', 'follow_up_time': '10:30'}
            for invalid in ('', '999999'):
                self.client.post(url, {**data, 'source': invalid})
                self.assertEqual(Call.objects.count(), count)
            self.client.post(url, {**data, 'source': self.other.pk})
            self.assertEqual(Call.objects.count(), count + 1)
            self.assertEqual(Call.objects.latest('pk').source_label_snapshot, 'منبع دوم')

    def test_standalone_call_form_requires_source_and_accepts_selection(self):
        data = {'caller_name': 'تست', 'call_number': '09125555555', 'call_type': 'incoming', 'status': 'answered', 'purpose': 'sale', 'duration': 0}
        self.assertIn('source', CallForm(data).errors)
        form = CallForm({**data, 'source': self.other.pk})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().source_label_snapshot, 'منبع دوم')

    def test_customer_detail_offers_active_sources_in_quick_call(self):
        result = self.client.get(reverse('customers:detail', args=[self.customer.pk]))
        self.assertEqual(result.status_code, 200)
        self.assertIn(self.other, list(result.context['filter_sources']))
        self.assertContains(result, '<select name="source" required')

    def test_inactive_source_is_hidden_and_cannot_be_selected_for_new_calls(self):
        self.other.is_active = False
        self.other.save()
        form = CallForm({'source': self.other.pk})
        self.assertIn('source', form.errors)
        response = self.client.get(reverse('customers:hub'))
        self.assertNotIn(self.other, list(response.context['filter_sources']))
        result = self.client.post(reverse('customers:quick_call', args=[self.customer.pk]), {'kind': 'new', 'notes': 'تست', 'source': self.other.pk})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(Call.objects.count(), 1)

    def test_existing_edit_without_source_preserves_its_original_value(self):
        data = {'caller_name': self.call.caller_name, 'call_number': self.call.call_number, 'call_type': 'incoming', 'status': 'busy', 'purpose': 'sale', 'duration': 0}
        self.rename()
        form = CallForm(data, instance=self.call)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(saved.source_label_snapshot, 'برچسب قدیمی')
        self.assertIn('source', CallForm({**data, 'source': ''}, instance=saved).errors)

    def test_deliberately_changing_record_source_captures_new_selected_source(self):
        self.call.source = self.other
        self.call.save(update_fields=['source'])
        self.call.refresh_from_db()
        self.assertEqual(self.call.source_label_snapshot, 'منبع دوم')

    def test_unattributed_legacy_calls_render_their_recorded_source(self):
        self.call.called_by = None
        self.call.created_by = None
        self.call.save(update_fields=['called_by', 'created_by'])
        for url in (reverse('calls:detail', args=[self.call.pk]), reverse('calls:list')):
            result = self.client.get(url)
            self.assertEqual(result.status_code, 200)
            self.assertContains(result, 'برچسب قدیمی')

    def test_html_report_and_excel_keep_old_and_new_labels_separate(self):
        self.rename()
        Ad.objects.create(platform=self.platform, process=self.process, source=self.source, cost=200, ad_number='NEW', created_by=self.admin)
        response = self.client.get(reverse('ads:list'))
        groups = response.context['report']['by_source']
        self.assertEqual({(row['source_label_snapshot'], row['total']) for row in groups}, {('برچسب قدیمی', Decimal('100')), ('برچسب جدید', Decimal('200'))})
        workbook = load_workbook(BytesIO(self.client.get(reverse('ads:export_report')).content))
        rows = list(workbook['تفکیک منبع هنگام ثبت'].values)
        self.assertIn(('09121111111', 'برچسب قدیمی', 1, 100), rows)
        self.assertIn(('09124444444', 'برچسب جدید', 1, 200), rows)
        result = self.client.get(reverse('calls:list'), {'q': 'برچسب قدیمی'})
        self.assertIn(self.call, list(result.context['page_obj']))

    def test_used_source_delete_is_rejected_and_unauthorized_edit_is_denied(self):
        self.client.post(reverse('ads:source_delete', args=[self.source.pk]))
        self.assertTrue(AdSource.objects.filter(pk=self.source.pk).exists())
        user = User.objects.create_user('source_outsider')
        self.client.force_login(user)
        response = self.client.post(reverse('ads:source_edit', args=[self.source.pk]), {'phone_number': '09120000000', 'label': 'تغییر غیرمجاز'})
        self.assertEqual(response.status_code, 403)
        self.source.refresh_from_db()
        self.assertEqual(self.source.label, 'برچسب قدیمی')
