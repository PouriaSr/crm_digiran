"""The registration tab replaces recruitment and has an independent permission."""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from accounts.models import UserPermissionOverride


class RegistrationTabPermissionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('recp_admin')
        cls.manager = User.objects.create_user('recp_mgr')
        cls.manager.groups.add(Group.objects.get_or_create(name='مدیر فروش')[0])
        cls.support = User.objects.create_user('recp_support')
        cls.support.groups.add(Group.objects.get_or_create(name='پشتیبان')[0])

    def setUp(self):
        self.hub = reverse('customers:hub')

    def test_admin_has_registration_tab(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(self.hub), '🔒 ثبت اطلاعات')

    def test_manager_has_all_hub_tabs(self):
        self.client.force_login(self.manager)
        self.assertEqual(set(self.client.get(self.hub).context['allowed_hub_tabs']), {'info', 'reception', 'case', 'registration', 'invoice'})

    def test_support_does_not_see_registration(self):
        self.client.force_login(self.support)
        response = self.client.get(self.hub)
        self.assertNotIn('registration', response.context['allowed_hub_tabs'])

    def test_support_direct_url_forbidden(self):
        self.client.force_login(self.support)
        self.assertEqual(self.client.get(self.hub, {'tab': 'registration'}).status_code, 403)

    def test_override_grants_registration_independently(self):
        UserPermissionOverride.objects.create(user=self.support, permission_key='customers.registration', granted=True)
        self.client.force_login(self.support)
        response = self.client.get(self.hub, {'tab': 'registration'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('case', response.context['allowed_hub_tabs'])
