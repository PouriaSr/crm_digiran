"""
تست‌های calls — منطق پیگیری، ارجاع تماس و دسترسی‌ها
"""
from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.urls import reverse

from .models import Call
from customers.models import Customer
from accounts.forms import ensure_groups, ROLE_GROUP_MAP


class CallLogicTest(TestCase):
    """تست منطق مدل تماس"""

    def test_followup_contradiction_auto_fix(self):
        """اگر is_followed_up=True باشد، وضعیت نباید followup بماند"""
        call = Call.objects.create(
            caller_name='تست',
            call_number='09120000000',
            status='followup',
            is_followed_up=True,
        )
        # مدل باید خودش وضعیت را به answered تغییر دهد
        self.assertEqual(call.status, 'answered')


class CallViewTest(TestCase):
    """تست‌های ویوها و دسترسی‌ها"""

    @classmethod
    def setUpTestData(cls):
        ensure_groups()
        cls.support = User.objects.create_user('support_call', password='t123456')
        cls.support.groups.add(Group.objects.get(name=ROLE_GROUP_MAP['support']))
        cls.call = Call.objects.create(caller_name='علی', call_number='09120000001', called_by=cls.support)

    def test_call_list_access(self):
        self.client.force_login(self.support)
        r = self.client.get(reverse('calls:list'))
        self.assertEqual(r.status_code, 200)

    def test_support_cannot_reassign_call_ajax(self):
        self.client.force_login(self.support)
        url = reverse('calls:reassign', args=[self.call.pk])
        response = self.client.post(
            url, 
            {'called_by': self.support.pk}, 
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()['success'])