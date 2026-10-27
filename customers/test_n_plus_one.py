"""
N+1 regression tests (v13e)
"""
from django.test import TestCase
from django.urls import reverse
from django.db import connection, reset_queries
from django.test.utils import override_settings
from django.contrib.auth.models import User

from customers.models import Customer


@override_settings(DEBUG=True)
class HubNPlusOneTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('hub_n_admin', password='t123456')
        cls.sales = User.objects.create_user('hub_n_sales', password='t123456')
        for i in range(5):
            Customer.objects.create(
                name=f'مشتری {i}',
                mobile=f'0912000000{i}',
                status='lead',
                source='direct',
                assigned_to=cls.sales,
                created_by=cls.admin,
            )

    def test_hub_query_count_is_bounded(self):
        """Hub should NOT do N+1 — query count must be roughly constant"""
        self.client.force_login(self.admin)
        reset_queries()
        response = self.client.get(reverse('customers:hub'))
        self.assertEqual(response.status_code, 200)
        queries = len(connection.queries)
        self.assertLess(
            queries, 30,
            f'N+1 detected: {queries} queries for 5 customers.'
        )
