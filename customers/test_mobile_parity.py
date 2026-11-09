"""Mobile exposes the same permitted operations and navigation as desktop."""
from html.parser import HTMLParser
from django.contrib.auth.models import User,Group
from django.test import TestCase
from django.urls import reverse
from accounts.models import UserPermissionOverride
from accounts.permissions import ROLE_TO_GROUP
from customers.models import Customer,FollowUp
from django.utils import timezone


class SurfaceParser(HTMLParser):
    def __init__(self):
        super().__init__();self.actions=[];self.capture=None;self.depth=0;self.links={'desktop':set(),'mobile':set()};self.surface=None;self.surface_tag=None;self.surface_depth=0
    def handle_starttag(self,tag,attrs):
        data=dict(attrs);classes=data.get('class','').split()
        if tag=='aside':self.surface='desktop';self.surface_tag='aside';self.surface_depth=1
        elif data.get('id')=='mobile-navigation' or 'app-bottom-nav' in classes:self.surface='mobile';self.surface_tag=tag;self.surface_depth=1
        elif self.surface and tag==self.surface_tag:self.surface_depth+=1
        if self.surface and tag=='a' and data.get('href'):self.links[self.surface].add(data['href'])
        if tag=='div' and 'crm-person-actions' in classes:self.capture=[];self.actions.append(self.capture);self.depth=1
        elif self.capture is not None and tag=='div':self.depth+=1
        if self.capture is not None and tag in ('a','button','form'):
            self.capture.append((tag,tuple((key,key in data if key=='disabled' else data.get(key)) for key in ('href','action','onclick','aria-label','disabled'))))
    def handle_endtag(self,tag):
        if self.capture is not None and tag=='div':
            self.depth-=1
            if not self.depth:self.capture=None
        if self.surface and tag==self.surface_tag:
            self.surface_depth-=1
            if not self.surface_depth:self.surface=None


class MobileParityTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_superuser('mobile_parity_admin')
        self.support=User.objects.create_user('mobile_parity_support')
        self.support.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['support'])[0])
        self.person=Customer.objects.create(name='مشتری گوشی',mobile='09128885551',source='direct',assigned_to=self.support)
        FollowUp.objects.create(customer=self.person,due_date=timezone.localdate(),created_by=self.support)

    def page(self,user):
        self.client.force_login(user)
        response=self.client.get(reverse('customers:hub'),{'tab':'info'})
        self.assertEqual(response.status_code,200)
        parsed=SurfaceParser();parsed.feed(response.content.decode())
        return response,parsed

    def test_customer_controls_match_for_manager_and_owner(self):
        for user in (self.admin,self.support):
            with self.subTest(user=user.username):
                response,parsed=self.page(user)
                self.assertEqual(len(parsed.actions),2)
                self.assertEqual(parsed.actions[0],parsed.actions[1])
                self.assertTemplateUsed(response,'customers/_customer_actions.html')
                mobile=response.content.decode().split('id="hub-mobile-list"',1)[1]
                self.assertIn('وضعیت پیگیری',mobile)
                self.assertIn('منبع جذب',mobile)
                self.assertIn(self.person.get_source_display(),mobile)
                self.assertIn('پیگیری باز',mobile)

    def test_all_sidebar_destinations_available_from_mobile(self):
        for user in (self.admin,self.support):
            with self.subTest(user=user.username):
                response,parsed=self.page(user)
                self.assertFalse(parsed.links['desktop']-parsed.links['mobile'])
                self.assertContains(response,'crm-task-launcher-bottom')
                self.assertContains(response,'id="mobile-navigation"')

    def test_advanced_denials_apply_to_mobile_controls_and_routes(self):
        UserPermissionOverride.objects.create(user=self.support,permission_key='hr.view_tasks',granted=False)
        response,parsed=self.page(self.support)
        self.assertNotContains(response,'crm-task-launcher-bottom"')
        self.assertNotIn(reverse('hr:task_list'),parsed.links['mobile'])
        self.assertNotIn(reverse('hr:attendance_list'),parsed.links['mobile'])
        self.assertEqual(self.client.get(reverse('hr:task_list')).status_code,403)
        self.assertFalse(any("deactivate" in str(token) for token in parsed.actions[1]))

    def test_candidate_only_permission_has_mobile_navigation_entry(self):
        UserPermissionOverride.objects.create(user=self.support,permission_key='customers.info',granted=False)
        self.client.force_login(self.support)
        response=self.client.get(reverse('customers:candidate_list'))
        self.assertEqual(response.status_code,200)
        parsed=SurfaceParser();parsed.feed(response.content.decode())
        self.assertIn(reverse('customers:candidate_list'),parsed.links['mobile'])
