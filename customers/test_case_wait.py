from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import User,Group
from django.urls import reverse
from django.utils import timezone
from accounts.models import UserPermissionOverride
from accounts.permissions import ROLE_TO_GROUP
from customers.models import Customer,Reception,CaseWorkSession


class CaseWaitTimingTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_superuser('case_wait_admin')
        self.client.force_login(self.user)
        self.person=Customer.objects.create(name='مراجعه پرونده',mobile='09127776601',assigned_to=self.user)
        self.ready=timezone.now()-timedelta(hours=1)
        self.rec=Reception.objects.create(customer=self.person,person_type='customer',referred_at=self.ready-timedelta(minutes=5),registration_completed_at=self.ready)

    def test_wait_ends_at_first_work_and_does_not_include_work_or_later_edits(self):
        first=self.ready+timedelta(minutes=20)
        CaseWorkSession.objects.create(reception=self.rec,started_at=first,ended_at=first+timedelta(minutes=10),started_by=self.user)
        CaseWorkSession.objects.create(reception=self.rec,started_at=first+timedelta(minutes=30),ended_at=first+timedelta(minutes=35),started_by=self.user)
        self.rec.case_completed_at=first+timedelta(minutes=10)
        self.rec.save(update_fields=['case_completed_at'])
        timing=self.rec.case_wait_timing
        self.assertEqual(timing['ended_at'],first)
        self.assertEqual(timing['display'],'00:20:00')
        self.assertFalse(timing['waiting'])
        page=self.client.get(reverse('customers:hub'),{'tab':'case','r':self.rec.pk})
        self.assertContains(page,'پایان انتظار:')
        self.assertContains(page,'مجموع انتظار')
        self.assertEqual(page.context['case_record'].case_wait_timing['seconds'],1200)

    def test_before_work_clock_is_live_but_read_does_not_start_or_complete_work(self):
        before=CaseWorkSession.objects.count()
        stamp=self.ready+timedelta(minutes=12)
        with patch('django.utils.timezone.now',return_value=stamp):
            self.assertEqual(self.rec.case_wait_timing['display'],'00:12:00')
            data=self.client.get(reverse('customers:case_clock'),{'receptions':[self.rec.pk]}).json()
        self.assertEqual(len(data['waiting']),1)
        self.assertIsNone(data['waiting'][0]['wait_ended_at'])
        self.assertEqual(CaseWorkSession.objects.count(),before)
        self.rec.refresh_from_db();self.assertIsNone(self.rec.case_completed_at)

    def test_old_order_uses_referral_and_missing_work_logs_remain_unknown(self):
        first=self.ready-timedelta(minutes=2)
        CaseWorkSession.objects.create(reception=self.rec,started_at=first,ended_at=first+timedelta(minutes=1))
        timing=self.rec.case_wait_timing
        self.assertTrue(timing['historical']);self.assertEqual(timing['seconds'],180)
        self.rec.work_sessions.all().delete()
        self.rec.case_completed_at=first;self.rec.save(update_fields=['case_completed_at'])
        timing=self.rec.case_wait_timing
        self.assertIsNone(timing['seconds']);self.assertIsNone(timing['ended_at'])
        self.assertFalse(timing['waiting'])

    def test_clock_honors_card_ownership_and_handles_bad_identifiers(self):
        other=User.objects.create_user('case_wait_other')
        other.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['support'])[0])
        UserPermissionOverride.objects.create(user=other,permission_key='customers.case',granted=True)
        self.client.force_login(other)
        response=self.client.get(reverse('customers:case_clock'),{'receptions':[self.rec.pk,'bad','-1']})
        self.assertEqual(response.status_code,200);self.assertEqual(response.json()['waiting'],[])
