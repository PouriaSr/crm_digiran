from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from accounts.models import UserPermissionOverride
from .forms import AdPlatformForm, AdProcessForm
from .models import Ad, AdPlatform, AdProcess, AdSource


class AdvertisingDefinitionEditingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('definition_admin', password='test-only')
        cls.platform = AdPlatform.objects.create(name='عنوان اولیه', ad_number_start=1000)
        cls.process = AdProcess.objects.create(platform=cls.platform, name='فرآیند اولیه', default_cost=1000)
        cls.source = AdSource.objects.create(phone_number='09123334444', label='خط اولیه')
        cls.ad = Ad.objects.create(platform=cls.platform, process=cls.process, source=cls.source, cost=1000, ad_number='1000', created_by=cls.admin)

    def setUp(self):
        self.client.force_login(self.admin)

    def edit_platform(self):
        return self.client.post(reverse('ads:platform_edit', args=[self.platform.pk]), {'name': 'عنوان ①٢３', 'ad_number_start': '２００１', 'is_active': 'on'})

    def edit_process(self):
        return self.client.post(reverse('ads:process_edit', args=[self.process.pk]), {'platform': self.platform.pk, 'name': 'فرآیند 𝟜५۶', 'default_cost': '۲٬۵۰۰', 'is_active': 'on'})

    def test_platform_can_be_edited_with_mixed_keyboard_digits(self):
        self.assertEqual(self.edit_platform().status_code, 302)
        self.platform.refresh_from_db()
        self.assertEqual(self.platform.name, 'عنوان 123')
        self.assertEqual(self.platform.ad_number_start, 2001)
        self.assertEqual(self.platform.get_next_ad_number(), '2001')
        body = self.client.get(reverse('ads:platform_list'))
        self.assertContains(body, 'عنوان ۱۲۳')
        self.assertContains(body, reverse('ads:platform_edit', args=[self.platform.pk]))

    def test_process_name_and_default_cost_can_be_edited(self):
        self.assertEqual(self.edit_process().status_code, 302)
        self.process.refresh_from_db()
        self.assertEqual(self.process.name, 'فرآیند 456')
        self.assertEqual(self.process.default_cost, Decimal('2500'))
        self.ad.refresh_from_db()
        self.assertEqual(self.ad.cost, Decimal('1000'))
        self.assertEqual(self.ad.process_name_snapshot, 'فرآیند اولیه')

    def test_renaming_definitions_keeps_historical_reports_and_excel(self):
        self.edit_platform()
        self.edit_process()
        self.platform.refresh_from_db()
        self.process.refresh_from_db()
        fresh = Ad.objects.create(platform=self.platform, process=self.process, source=self.source, cost=2500, ad_number='2001', created_by=self.admin)
        self.ad.note = 'ویرایش توضیحات'
        self.ad.save()
        self.assertEqual(self.ad.platform_name_snapshot, 'عنوان اولیه')
        self.assertEqual(self.ad.process_name_snapshot, 'فرآیند اولیه')
        self.assertEqual(fresh.platform_name_snapshot, 'عنوان 123')
        self.assertEqual(fresh.process_name_snapshot, 'فرآیند 456')
        result = self.client.get(reverse('ads:list'))
        groups = result.context['report']['by_platform']
        self.assertEqual({(row['platform__name'], row['count']) for row in groups}, {('عنوان اولیه', 1), ('عنوان 123', 1)})
        old_search = self.client.get(reverse('ads:list'), {'q': 'عنوان اولیه'})
        self.assertEqual(list(old_search.context['page_obj']), [self.ad])
        workbook = load_workbook(BytesIO(self.client.get(reverse('ads:export_report')).content))
        rows = list(workbook['ریز تبلیغات'].values)
        self.assertEqual({(row[1], row[2]) for row in rows[1:]}, {('عنوان اولیه', 'فرآیند اولیه'), ('عنوان 123', 'فرآیند 456')})

    def test_used_process_cannot_be_moved_to_another_platform(self):
        other = AdPlatform.objects.create(name='عنوان دیگر')
        response = self.client.post(reverse('ads:process_edit', args=[self.process.pk]), {'platform': other.pk, 'name': 'جابه‌جایی', 'default_cost': 1000, 'is_active': 'on'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('platform', response.context['form'].errors)
        self.process.refresh_from_db()
        self.assertEqual(self.process.platform_id, self.platform.pk)

    def test_unused_process_can_be_moved(self):
        unused = AdProcess.objects.create(platform=self.platform, name='بدون تبلیغ', default_cost=100)
        other = AdPlatform.objects.create(name='عنوان دیگر')
        response = self.client.post(reverse('ads:process_edit', args=[unused.pk]), {'platform': other.pk, 'name': unused.name, 'default_cost': 500, 'is_active': 'on'})
        self.assertEqual(response.status_code, 302)
        unused.refresh_from_db()
        self.assertEqual(unused.platform_id, other.pk)

    def test_duplicate_names_treat_keyboard_digits_as_equivalent(self):
        AdPlatform.objects.create(name='عنوان ①۲３')
        form = AdPlatformForm({'name': 'عنوان 123', 'ad_number_start': 1000, 'is_active': True})
        self.assertIn('name', form.errors)
        AdProcess.objects.create(platform=self.platform, name='فرآیند ①۲３', default_cost=100)
        form = AdProcessForm({'platform': self.platform.pk, 'name': 'فرآیند 123', 'default_cost': 100})
        self.assertIn('name', form.errors)

    def test_permission_denial_and_explicit_advanced_grant(self):
        user = User.objects.create_user('definition_operator')
        self.client.force_login(user)
        urls = (reverse('ads:platform_edit', args=[self.platform.pk]), reverse('ads:process_edit', args=[self.process.pk]))
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {'name': 'غیرمجاز'}).status_code, 403)
        UserPermissionOverride.objects.create(user=user, permission_key='ads.manage_defs', granted=True)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.edit_platform().status_code, 302)

    def test_invalid_cost_does_not_partially_save_edits(self):
        result = self.client.post(reverse('ads:process_edit', args=[self.process.pk]), {'platform': self.platform.pk, 'name': 'نباید ذخیره شود', 'default_cost': '-۱'})
        self.assertEqual(result.status_code, 200)
        self.process.refresh_from_db()
        self.assertEqual(self.process.name, 'فرآیند اولیه')
