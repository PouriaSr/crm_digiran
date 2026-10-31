from ads.models import AdSource
from datetime import datetime, timedelta, time, timezone as utc_timezone
from unittest.mock import patch
import jdatetime
from django.contrib.auth.models import User, Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import UserPermissionOverride
from calls.models import Call
from customers.models import Customer, FollowUp


def jdate(value):
    return jdatetime.date.fromgregorian(date=value).strftime('%Y/%m/%d')


class CardWorkflowTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('cw-admin', password='password')
        cls.owner = cls.user('cw-owner', 'کارشناس فروش')
        cls.peer = cls.user('cw-peer', 'کارشناس فروش')
        cls.manager = cls.user('cw-manager', 'مدیر فروش')
        cls.supervisor = cls.user('cw-supervisor', 'سرپرست')
        cls.customer = Customer.objects.create(name='مشتری مشترک', mobile='09127778888', assigned_to=cls.owner, created_by=cls.admin)
        cls.call = Call.objects.create(customer=cls.customer, caller_name=cls.customer.name, call_number=cls.customer.mobile, notes='شرح قبلی', called_by=cls.peer)

    @staticmethod
    def user(name, group):
        user = User.objects.create_user(name, password='password')
        user.groups.add(Group.objects.get_or_create(name=group)[0])
        return user

    def setUp(self):
        self.client.force_login(self.peer)
        self.quick = reverse('customers:quick_call', args=[self.customer.pk])

    def test_non_owner_cannot_edit_customer_or_calls_through_any_endpoint(self):
        for url, data in [
            (reverse('customers:edit', args=[self.customer.pk]), {'name':'نام دیگر','mobile':self.customer.mobile,'notes':'ویرایش','source':'direct'}),
            (reverse('customers:hub_call_edit', args=[self.call.pk]), {'notes':'ویرایش','status':'busy'}),
            (reverse('calls:edit', args=[self.call.pk]), {'notes':'ویرایش'}),
        ]:
            with self.subTest(url=url):
                response = self.client.post(url, data)
                self.assertEqual(response.status_code, 403)
        self.customer.refresh_from_db(); self.call.refresh_from_db()
        self.assertEqual(self.customer.name, 'مشتری مشترک')
        self.assertEqual(self.call.notes, 'شرح قبلی')

    def test_owner_admin_and_both_supervisor_groups_can_edit(self):
        for user in (self.owner, self.manager, self.supervisor, self.admin):
            self.client.force_login(user)
            response = self.client.post(reverse('customers:hub_call_edit', args=[self.call.pk]), {'notes':'شرح اصلاحی','status':'busy','purpose':'support'})
            self.assertEqual(response.status_code, 302)
            self.call.refresh_from_db()
            self.assertEqual(self.call.notes, 'شرح اصلاحی')
            self.assertEqual(self.call.status, 'busy')
            self.assertEqual(self.client.get(reverse('customers:edit', args=[self.customer.pk])).status_code, 200)
            self.assertEqual(self.client.get(reverse('calls:edit', args=[self.call.pk])).status_code, 200)

    def test_call_author_is_not_automatically_card_owner(self):
        self.assertEqual(self.call.called_by_id, self.peer.pk)
        response = self.client.post(reverse('customers:hub_call_edit', args=[self.call.pk]), {'notes':'نامعتبر'})
        self.assertEqual(response.status_code, 403)

    def test_permission_override_does_not_bypass_ownership_or_transfer_role(self):
        for permission in ('customers.edit','calls.edit','calls.reassign'):
            UserPermissionOverride.objects.create(user=self.peer, permission_key=permission, granted=True)
        self.assertEqual(self.client.post(reverse('customers:hub_call_edit', args=[self.call.pk]), {'notes':'تلاش'}).status_code, 403)
        self.assertEqual(self.client.post(reverse('customers:reassign', args=[self.customer.pk]), {'assigned_to':self.peer.pk}).status_code, 403)
        self.assertEqual(self.client.post(reverse('calls:reassign', args=[self.call.pk]), {'called_by':self.peer.pk}).status_code, 403)

    def test_card_owner_cannot_transfer_but_manager_can_and_old_owner_loses_access(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse('customers:reassign', args=[self.customer.pk]), {'assigned_to':self.peer.pk}).status_code, 403)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(reverse('customers:reassign', args=[self.customer.pk]), {'assigned_to':self.peer.pk}).status_code, 302)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('customers:edit', args=[self.customer.pk])).status_code, 403)
        self.client.force_login(self.peer)
        self.assertEqual(self.client.get(reverse('customers:edit', args=[self.customer.pk])).status_code, 200)

    def test_owner_cannot_transfer_by_posting_assigned_to_in_profile_form(self):
        UserPermissionOverride.objects.create(user=self.owner, permission_key='customers.profile_full', granted=True)
        self.client.force_login(self.owner)
        self.client.post(reverse('customers:edit', args=[self.customer.pk]), {'name':self.customer.name,'mobile':self.customer.mobile,'notes':'توضیح','source':'direct','assigned_to':self.peer.pk})
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.assigned_to_id, self.owner.pk)

    def test_peer_can_add_call_with_independent_type_purpose_and_status(self):
        response = self.client.post(self.quick, {'kind':'new','contact_type':'divar','purpose':'support','status':'busy','notes':'تماس همکار'})
        self.assertEqual(response.status_code, 302)
        call = Call.objects.latest('pk')
        self.assertEqual((call.contact_type,call.purpose,call.status), ('divar','support','busy'))
        self.assertEqual(call.called_by_id, self.peer.pk)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.assigned_to_id, self.owner.pk)

    def test_operator_accountant_and_ads_roles_can_register_on_a_colleagues_card(self):
        for index, group in enumerate(('اپراتور', 'حسابدار', 'مسئول تبلیغات')):
            user = self.user(f'cw-extra-{index}', group)
            self.client.force_login(user)
            self.client.post(self.quick, {'kind':'new', 'notes':'تماس همکار', 'contact_type':'incoming'})
            self.assertEqual(Call.objects.latest('pk').called_by_id, user.pk)
            self.client.post(self.quick, {'kind':'followup', 'notes':'پیگیری همکار', 'follow_up_date':jdate(timezone.localdate()), 'follow_up_time':'12:30'})
            call = Call.objects.latest('pk')
            self.assertEqual(call.called_by_id, user.pk)
            self.assertEqual(call.contact_type, 'followup')
            self.assertEqual(self.client.post(reverse('customers:hub_call_edit', args=[call.pk]), {'notes':'ویرایش غیرمجاز'}).status_code, 403)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.assigned_to_id, self.owner.pk)

    def test_followup_requires_both_date_and_time_before_any_write(self):
        for date, clock in [(jdate(timezone.localdate()),''), ('','14:30'), (jdate(timezone.localdate()),'25:00'), (jdate(timezone.localdate()),'14:99')]:
            with self.subTest(date=date,clock=clock):
                self.client.post(self.quick, {'kind':'followup','notes':'باید رد شود','follow_up_date':date,'follow_up_time':clock})
                self.assertEqual(Call.objects.count(),1)
                self.assertFalse(FollowUp.objects.exists())
        self.customer.refresh_from_db()
        self.assertIsNone(self.customer.notes)

    def test_followup_records_due_time_separately_from_server_creation_time(self):
        before = timezone.now()
        self.client.post(self.quick, {'kind':'followup','notes':'پیگیری همکار','follow_up_date':jdate(timezone.localdate()),'follow_up_time':'۱۴:۳۰','call_date':'2000-01-01','needs_next':'1','next_follow_up_date':jdate(timezone.localdate()+timedelta(days=2)),'next_follow_up_time':'09:15'})
        call = Call.objects.latest('pk')
        self.assertEqual(call.follow_up_time, time(14,30))
        self.assertGreaterEqual(call.call_date,before)
        self.assertLessEqual(call.call_date,timezone.now())
        pending = FollowUp.objects.get(is_done=False)
        self.assertEqual(pending.due_time,time(9,15))
        self.assertGreaterEqual(pending.created_at,before)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.assigned_to_id,self.owner.pk)

    def test_missing_next_time_does_not_close_existing_task(self):
        fu = FollowUp.objects.create(customer=self.customer,due_date=timezone.localdate(),due_time=time(10))
        self.client.post(self.quick, {'kind':'followup','notes':'رد','follow_up_date':jdate(timezone.localdate()),'follow_up_time':'10:00','needs_next':'1','next_follow_up_date':jdate(timezone.localdate()+timedelta(days=1))})
        fu.refresh_from_db()
        self.assertFalse(fu.is_done)
        self.assertEqual(Call.objects.count(),1)

    def test_purchase_intent_without_followup_time_cannot_create_customer(self):
        self.client.post(reverse('customers:hub_submit_call'), {'purpose':'sale', 'call_status':'answered', 'requested_condition':'cash', 'source':AdSource.objects.get_or_create(phone_number='09129999888', defaults={'label':'تست'})[0].pk, 'mobile':'09126667777','name':'مشتری نو','call_type':'incoming','notes':'تست','customer_analysis':'potential','follow_up_date':jdate(timezone.localdate())})
        self.assertFalse(Customer.objects.filter(mobile='09126667777').exists())

    def test_legacy_history_without_a_registered_caller_renders(self):
        self.call.called_by = None
        self.call.follow_up_date = timezone.localdate()
        self.call.follow_up_time = None
        self.call.save()
        response = self.client.get(reverse('customers:hub'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'بدون ساعت')
        self.assertContains(response, 'ثبت‌کننده:')

    def test_history_and_ui_respect_card_owner(self):
        response = self.client.get(reverse('customers:hub'))
        self.assertContains(response,'کارشناس تماس')
        self.assertContains(response,'انتقال غیرفعال')
        self.assertNotContains(response,'onclick="openCallEdit(this)"')
        self.assertNotContains(response,'onclick="openCustomerModal(')
        self.client.force_login(self.owner)
        response = self.client.get(reverse('customers:hub'))
        self.assertContains(response,'onclick="openCallEdit(this)"')
        self.assertContains(response,'onclick="openCustomerModal(')


class FollowupPriorityFilterTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin=User.objects.create_superuser('priority-admin',password='password')
        cls.now=datetime(2026,10,27,8,30,tzinfo=utc_timezone.utc) # noon Tehran
        cls.today=cls.now.astimezone(timezone.get_default_timezone()).date()
        cls.cards=[]
        for index,(offset,clock) in enumerate([(-1,time(15)),(0,time(10)),(0,time(14)),(1,time(9)),(None,None)]):
            c=Customer.objects.create(name='مشتری',mobile=f'0912111000{index}',assigned_to=cls.admin)
            cls.cards.append(c)
            if offset is not None:
                FollowUp.objects.create(customer=c,due_date=cls.today+timedelta(days=offset),due_time=clock)

    def setUp(self):
        self.client.force_login(self.admin)
        self.freeze=patch('django.utils.timezone.now',return_value=self.now)
        self.freeze.start();self.addCleanup(self.freeze.stop)

    def rows(self, **filters):
        response=self.client.get(reverse('customers:hub'), filters)
        self.assertEqual(response.status_code,200)
        return [c.pk for c in response.context['customers']]

    def test_default_order_is_overdue_today_future_then_no_task(self):
        self.assertEqual(self.rows(),[c.pk for c in self.cards])

    def test_overdue_includes_today_past_hours(self):
        self.assertEqual(self.rows(priority='overdue'),[c.pk for c in self.cards[:2]])
        self.assertEqual(self.rows(priority='none'),[self.cards[4].pk])

    def test_date_range_is_inclusive_and_preserves_sort(self):
        day=jdate(self.today)
        self.assertEqual(self.rows(date_field='followup',date_from=day,date_to=day),[self.cards[1].pk,self.cards[2].pk])
        self.assertEqual(self.rows(date_field='followup',date_from=jdate(self.today+timedelta(days=2))),[])
        self.assertEqual(self.rows(date_field='followup',date_from='wrong'),[])

    def test_pending_counter_uses_open_tasks_not_call_history(self):
        response = self.client.get(reverse('customers:hub'))
        self.assertEqual(response.context['stats']['pending_followups'], 3)
        FollowUp.objects.filter(customer=self.cards[0]).update(is_done=True)
        response = self.client.get(reverse('customers:hub'))
        self.assertEqual(response.context['stats']['pending_followups'], 2)

    def test_filter_does_not_offer_duplicate_customer_creation(self):
        c = self.cards[4]
        c.name = 'شناسه یکتا'
        c.save(update_fields=['name'])
        response = self.client.get(reverse('customers:hub'), {'q': c.mobile, 'priority': 'today'})
        self.assertFalse(response.context['show_new'])
        self.assertEqual(list(response.context['customers']), [])

    def test_earliest_task_date_and_time_come_from_same_record(self):
        c=self.cards[4]
        FollowUp.objects.create(customer=c,due_date=self.today+timedelta(days=2),due_time=time(8))
        FollowUp.objects.create(customer=c,due_date=self.today+timedelta(days=1),due_time=time(17))
        response=self.client.get(reverse('customers:hub'))
        row=next(x for x in response.context['customers'] if x.pk==c.pk)
        self.assertEqual(row.open_fu_due,self.today+timedelta(days=1))
        self.assertEqual(row.open_fu_time,time(17))
