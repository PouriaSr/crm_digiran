"""Regression tests for v12 UserEditForm fix"""
from django.test import TestCase
from django.contrib.auth.models import User
from accounts.forms import UserEditForm
from accounts.models import UserPermissionOverride
from accounts.permissions import PERMISSION_META


class UserEditFormSuperuserOverrideTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('reg_edit', password='t123456')
        UserPermissionOverride.objects.create(
            user=cls.user, permission_key='customers.view', granted=False,
        )

    def test_promote_to_superuser_clears_overrides(self):
        data = {
            'username': self.user.username,
            'first_name': '', 'last_name': '', 'email': '',
            'role': 'admin',
            'is_active': True,
        }
        for pk in PERMISSION_META.keys():
            data['perm__' + pk.replace('.', '_')] = 'inherit'

        form = UserEditForm(data=data, instance=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_superuser)
        self.assertEqual(self.user.permission_overrides.count(), 0,
                         "overrideها باید پاک بشن")
