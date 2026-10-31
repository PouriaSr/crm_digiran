from django.contrib.auth.models import User, Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import UserPermissionOverride
from customers.models import Customer, Reception, HiringAd, HiringApplication, CaseWorkSession, InterviewSession


class LiveSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin=User.objects.create_superuser('live_search_admin')
        cls.owner=User.objects.create_user('live_search_owner')
        cls.owner.groups.add(Group.objects.get_or_create(name='اپراتور')[0])
        UserPermissionOverride.objects.create(user=cls.owner,permission_key='customers.hiring',granted=True)
        cls.ad=HiringAd.objects.create(platform='jobinja',number=2000,role_key='role:sales',role_title='کارشناس فروش',email='jobs@example.test',created_by=cls.admin)
        cls.customer=Customer.objects.create(name='کارجوی جستجوی لحظه‌ای',mobile='09120012345',assigned_to=cls.owner)
        cls.rec=Reception.objects.create(customer=cls.customer,person_type='interviewer',arrived_at=timezone.now(),referred_at=timezone.now())
        HiringApplication.objects.create(reception=cls.rec,job_ad=cls.ad)

    def setUp(self):self.client.force_login(self.admin)

    def test_ads_are_on_hiring_page_with_independent_search_and_pagination(self):
        for query in ('۲۰۰۰','٢٠٠٠','2000','فروش','جابینجا','jobs@example.test'):
            response=self.client.get(reverse('customers:hub'),{'tab':'hiring','ad_q':query,'workflow_q':'نام کارجوی ناموجود'})
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'id="hiring-ad-results"')
            self.assertEqual(response.context['hiring_ads'].paginator.count,1)
            self.assertEqual(response.context['hiring_records'].paginator.count,0)
        response=self.client.get(reverse('customers:hub'),{'tab':'hiring','ad_q':'نام آگهی ناموجود'})
        self.assertEqual(response.context['hiring_ads'].paginator.count,0)

    def test_search_preserves_owner_boundary_and_document_denial(self):
        self.client.force_login(self.owner)
        foreign=Customer.objects.create(name='کارجوی دیگر',mobile='09123333333',assigned_to=self.admin)
        rec=Reception.objects.create(customer=foreign,person_type='interviewer',referred_at=timezone.now())
        HiringApplication.objects.create(reception=rec,job_ad=self.ad)
        response=self.client.get(reverse('customers:hub'),{'tab':'hiring'},HTTP_X_LIVE_SEARCH='1')
        self.assertEqual(response.context['hiring_ads'][0].applicant_count,1)
        self.assertEqual(response.context['hiring_records'].paginator.count,1)
        self.assertNotContains(response,foreign.name)

    def test_live_get_does_not_start_clocks_or_mutate_admission(self):
        before=(CaseWorkSession.objects.count(),InterviewSession.objects.count(),self.rec.updated_at)
        for query in ('کارجو','۰۹۱۲۰۰۱۲۳۴۵','هیچ'):
            self.client.get(reverse('customers:hub'),{'tab':'hiring','workflow_q':query},HTTP_X_LIVE_SEARCH='1')
        self.rec.refresh_from_db()
        self.assertEqual(before,(CaseWorkSession.objects.count(),InterviewSession.objects.count(),self.rec.updated_at))

    def test_all_existing_list_searches_have_results_regions_and_shared_client(self):
        for name in ('customers:inactive_list','products:list','products:category_list','calls:list','sales:list','accounts:user_list','hr:employee_list','hr:task_list','hr:leave_list','audit:list','ads:list'):
            with self.subTest(name=name):
                response=self.client.get(reverse(name),{'q':'جستجوی بدون نتیجه'},HTTP_X_LIVE_SEARCH='1')
                self.assertEqual(response.status_code,200)
                self.assertContains(response,'id="crm-list-results"')
                self.assertContains(response,'window.CRMLiveSearch=')

    def test_global_search_and_admin_use_shared_client(self):
        response=self.client.get(reverse('dashboard:search'),{'q':'کارجوی'})
        self.assertContains(response,'id="global-search-results"')
        self.assertContains(response,self.customer.name)
        self.assertContains(self.client.get('/admin/customers/customer/',{'q':'کارجوی'}),'window.CRMLiveSearch=')
