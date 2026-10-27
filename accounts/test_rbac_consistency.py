"""RBAC consistency tests (v13a)"""
from django.test import TestCase
from accounts.permissions import (
    PERMISSIONS, PERMISSION_META, ROLE_TO_GROUP, ROLE_ADMIN,
)


class RBACConsistencyTest(TestCase):
    def test_permissions_and_meta_have_same_keys(self):
        only_perm = set(PERMISSIONS) - set(PERMISSION_META)
        only_meta = set(PERMISSION_META) - set(PERMISSIONS)
        self.assertEqual(only_perm, set(),
                         f'PERMISSIONS without META: {sorted(only_perm)}')
        self.assertEqual(only_meta, set(),
                         f'META without PERMISSIONS: {sorted(only_meta)}')

    def test_all_roles_are_known(self):
        all_roles = {ROLE_ADMIN} | set(ROLE_TO_GROUP.keys())
        for perm, roles in PERMISSIONS.items():
            for role in roles:
                self.assertIn(role, all_roles,
                              f'PERMISSIONS[{perm!r}] unknown role: {role!r}')

    def test_no_empty_role_lists(self):
        for perm, roles in PERMISSIONS.items():
            self.assertGreater(len(roles), 0,
                               f'PERMISSIONS[{perm!r}] empty')

    def test_meta_is_valid_tuple(self):
        for perm, meta in PERMISSION_META.items():
            self.assertIsInstance(meta, tuple)
            self.assertGreaterEqual(len(meta), 2)
            for idx, item in enumerate(meta):
                self.assertIsInstance(item, str)
