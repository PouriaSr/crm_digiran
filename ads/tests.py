from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.permissions import ROLE_ADS_MANAGER, ROLE_TO_GROUP
from products.models import Category, Product

from .models import Ad, AdLog, AdPlatform, AdProcess, AdSource


class AdTestCase(TestCase):
    """تست‌های اپ تبلیغات"""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username='ads_admin', password='test1234', email='a@test.com',
        )
        cls.manager = User.objects.create_user(
            username='ads_manager_user', password='test1234',
        )
        # ✅ FIX: استفاده از گروه فارسی مطابق ROLE_TO_GROUP
        grp, _ = Group.objects.get_or_create(
            name=ROLE_TO_GROUP[ROLE_ADS_MANAGER],
        )
        cls.manager.groups.add(grp)

        cls.outsider = User.objects.create_user(
            username='outsider', password='test1234',
        )
        # ✅ FIX: اطمینان از فعال بودن کاربر
        cls.outsider.is_active = True
        cls.outsider.save(update_fields=['is_active'])

        # داده‌های پایه
        cls.platform_divar = AdPlatform.objects.create(name='دیوار')
        cls.platform_basalam = AdPlatform.objects.create(name='باسلام')

        cls.process_nardeban = AdProcess.objects.create(
            platform=cls.platform_divar,
            name='نردبان',
            default_cost=Decimal('50000'),
        )
        cls.process_pele = AdProcess.objects.create(
            platform=cls.platform_divar,
            name='پله',
            default_cost=Decimal('30000'),
        )
        cls.process_cpc = AdProcess.objects.create(
            platform=cls.platform_basalam,
            name='کمپین کلیکی',
            default_cost=Decimal('20000'),
        )

        cls.source1 = AdSource.objects.create(
            phone_number='09120000001', label='خط اصلی',
        )

        cls.category = Category.objects.create(name='تست')
        cls.product = Product.objects.create(
            name='محصول تستی',
            category=cls.category,
            price=Decimal('100000'),
            stock=10,
        )

    def setUp(self):
        self.client = Client()

    # ─── دسترسی ───
    def test_anonymous_redirected(self):
        r = self.client.get(reverse('ads:list'))
        self.assertEqual(r.status_code, 302)

    def test_outsider_forbidden(self):
        # ✅ FIX: force_login — Django docs برای تست‌ها توصیه می‌کنه
        # و چک‌های backend/is_active رو دور می‌زنه
        self.client.force_login(self.outsider)
        r = self.client.get(reverse('ads:list'))
        self.assertEqual(r.status_code, 403)

    def test_manager_can_view_list(self):
        self.client.force_login(self.manager)
        r = self.client.get(reverse('ads:list'))
        self.assertEqual(r.status_code, 200)

    def test_admin_can_view_list(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse('ads:list'))
        self.assertEqual(r.status_code, 200)

    # ─── ایجاد ───
    def test_create_ad(self):
        self.client.force_login(self.manager)
        r = self.client.post(reverse('ads:create'), {
            'platform': self.platform_divar.id,
            'process': self.process_nardeban.id,
            'cost': '50000',
            'source': self.source1.id,
            'product': self.product.id,
            'ad_number': '12345678',
            'note': 'تست',
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Ad.objects.count(), 1)
        ad = Ad.objects.first()
        self.assertEqual(ad.created_by, self.manager)
        self.assertEqual(ad.ad_number, '12345678')

    def test_create_ad_creates_log(self):
        self.client.force_login(self.manager)
        self.client.post(reverse('ads:create'), {
            'platform': self.platform_divar.id,
            'process': self.process_nardeban.id,
            'cost': '50000',
            'source': self.source1.id,
            'ad_number': '12345678',
        })
        self.assertEqual(AdLog.objects.filter(action='create').count(), 1)

    def test_duplicate_ad_number_blocked(self):
        Ad.objects.create(
            platform=self.platform_divar,
            process=self.process_nardeban,
            cost=Decimal('50000'),
            source=self.source1,
            ad_number='DUP-001',
            created_by=self.manager,
        )
        self.client.force_login(self.manager)
        r = self.client.post(reverse('ads:create'), {
            'platform': self.platform_divar.id,
            'process': self.process_nardeban.id,
            'cost': '50000',
            'source': self.source1.id,
            'ad_number': 'DUP-001',
        })
        self.assertEqual(r.status_code, 200)  # form error, not redirect
        self.assertEqual(Ad.objects.count(), 1)
        self.assertContains(r, 'قبلاً ثبت شده')

    def test_process_mismatch_blocked(self):
        self.client.force_login(self.manager)
        r = self.client.post(reverse('ads:create'), {
            'platform': self.platform_divar.id,
            'process': self.process_cpc.id,  # متعلق به باسلام
            'cost': '20000',
            'source': self.source1.id,
            'ad_number': 'MIS-001',
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Ad.objects.count(), 0)

    # ─── ویرایش ───
    def test_edit_creates_update_log(self):
        ad = Ad.objects.create(
            platform=self.platform_divar,
            process=self.process_nardeban,
            cost=Decimal('50000'),
            source=self.source1,
            ad_number='EDIT-001',
            created_by=self.manager,
        )
        self.client.force_login(self.manager)
        r = self.client.post(reverse('ads:edit', args=[ad.pk]), {
            'platform': self.platform_divar.id,
            'process': self.process_pele.id,
            'cost': '30000',
            'source': self.source1.id,
            'ad_number': 'EDIT-001',
        })
        self.assertEqual(r.status_code, 302)
        ad.refresh_from_db()
        self.assertEqual(ad.process, self.process_pele)
        log = AdLog.objects.filter(ad=ad, action='update').first()
        self.assertIsNotNone(log)
        self.assertIn('process', log.changes)

    def test_manager_cannot_edit_others_ad(self):
        ad = Ad.objects.create(
            platform=self.platform_divar,
            process=self.process_nardeban,
            cost=Decimal('50000'),
            source=self.source1,
            ad_number='OTHER-001',
            created_by=self.admin,
        )
        self.client.force_login(self.manager)
        r = self.client.get(reverse('ads:edit', args=[ad.pk]))
        self.assertEqual(r.status_code, 403)

    # ─── حذف ───
    def test_manager_cannot_delete(self):
        ad = Ad.objects.create(
            platform=self.platform_divar,
            process=self.process_nardeban,
            cost=Decimal('50000'),
            source=self.source1,
            ad_number='DEL-001',
            created_by=self.manager,
        )
        self.client.force_login(self.manager)
        r = self.client.post(reverse('ads:delete', args=[ad.pk]))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Ad.objects.count(), 1)

    def test_admin_can_delete(self):
        ad = Ad.objects.create(
            platform=self.platform_divar,
            process=self.process_nardeban,
            cost=Decimal('50000'),
            source=self.source1,
            ad_number='DEL-002',
            created_by=self.manager,
        )
        self.client.force_login(self.admin)
        r = self.client.post(reverse('ads:delete', args=[ad.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Ad.objects.count(), 0)

    # ─── گزارش ───
    def test_manager_sees_only_own_ads(self):
        Ad.objects.create(
            platform=self.platform_divar, process=self.process_nardeban,
            cost=Decimal('50000'), source=self.source1,
            ad_number='MINE', created_by=self.manager,
        )
        Ad.objects.create(
            platform=self.platform_divar, process=self.process_nardeban,
            cost=Decimal('50000'), source=self.source1,
            ad_number='NOT-MINE', created_by=self.admin,
        )
        self.client.force_login(self.manager)
        r = self.client.get(reverse('ads:list'))
        self.assertContains(r, 'MINE')
        self.assertNotContains(r, 'NOT-MINE')

    def test_admin_sees_all_ads(self):
        Ad.objects.create(
            platform=self.platform_divar, process=self.process_nardeban,
            cost=Decimal('50000'), source=self.source1,
            ad_number='A1', created_by=self.manager,
        )
        Ad.objects.create(
            platform=self.platform_divar, process=self.process_nardeban,
            cost=Decimal('50000'), source=self.source1,
            ad_number='A2', created_by=self.admin,
        )
        self.client.force_login(self.admin)
        r = self.client.get(reverse('ads:list'))
        self.assertContains(r, 'A۱')
        self.assertContains(r, 'A۲')

    # ─── سرچ ───
    def test_search_by_ad_number(self):
        Ad.objects.create(
            platform=self.platform_divar, process=self.process_nardeban,
            cost=Decimal('50000'), source=self.source1,
            ad_number='SEARCH-999', created_by=self.manager,
        )
        self.client.force_login(self.manager)
        r = self.client.get(reverse('ads:list'), {'q': 'SEARCH-999'})
        self.assertContains(r, 'SEARCH-999')

    # ─── Pagination ───
    def test_pagination_10_per_page(self):
        for i in range(15):
            Ad.objects.create(
                platform=self.platform_divar, process=self.process_nardeban,
                cost=Decimal('50000'), source=self.source1,
                ad_number=f'PAG-{i:03d}', created_by=self.manager,
            )
        self.client.force_login(self.manager)
        r = self.client.get(reverse('ads:list'))
        self.assertEqual(len(r.context['page_obj']), 10)
        self.assertTrue(r.context['page_obj'].has_next())

    # ─── مدیریت (ادمین) ───
    def test_manager_cannot_manage_platforms(self):
        self.client.force_login(self.manager)
        r = self.client.get(reverse('ads:platform_list'))
        self.assertEqual(r.status_code, 403)

    def test_admin_can_create_platform(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse('ads:platform_list'), {
            'name': 'شیپور',
            'ad_number_start': 1000,
            'is_active': True,
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(AdPlatform.objects.filter(name='شیپور').exists())

    def test_cannot_delete_platform_in_use(self):
        Ad.objects.create(
            platform=self.platform_divar, process=self.process_nardeban,
            cost=Decimal('50000'), source=self.source1,
            ad_number='INUSE', created_by=self.manager,
        )
        self.client.force_login(self.admin)
        r = self.client.post(reverse('ads:platform_delete', args=[self.platform_divar.pk]))
        self.assertTrue(AdPlatform.objects.filter(pk=self.platform_divar.pk).exists())