from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import UserPermissionOverride
from accounts.permissions import ROLE_TO_GROUP
from .admin import TestRunAdmin
from .forms import MessageTemplateForm, SimulationForm
from .models import ChannelConfiguration, MessageTemplate, TestRun


class MessagingManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('message_admin', password='test-password')
        self.manager = User.objects.create_user('message_manager', password='test-password')
        self.manager.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['sales_manager'])[0])
        self.outsider = User.objects.create_user('message_other', password='test-password')
        self.url = reverse('communications:center')
        self.sms_template = MessageTemplate.objects.filter(channel='sms', is_active=True).first()

    def config_data(self, **changes):
        data = {'action': 'save_configuration', 'config-provider': 'custom', 'config-sender': '1000123',
                'config-credential_env': 'SMS_API_KEY', 'config-endpoint': 'https://example.com/api'}
        data.update(changes)
        return data

    def template_data(self, **changes):
        data = {'action': 'save_template', 'template-name': 'قالب اختصاصی', 'template-category': 'followup',
                'template-body': 'سلام {customer_name}، {task_title}', 'template-is_active': 'on'}
        data.update(changes)
        return data

    def simulation_data(self, template=None, **changes):
        data = {'action': 'simulate', 'simulation-template': str((template or self.sms_template).pk),
                'simulation-recipient': '۰۹۱۲۳۴۵۶۷۸۹', 'simulation-sample_name': '<script>نام</script>',
                'simulation-company_name': 'دیجیران', 'simulation-task_title': 'پیگیری آزمایشی',
                'simulation-custom_text': 'متن دلخواه کاربر'}
        data.update(changes)
        return data

    def test_seeded_templates_are_varied_for_all_active_channels(self):
        for channel in ('sms', 'email', 'whatsapp'):
            items = MessageTemplate.objects.filter(channel=channel, is_suggested=True)
            self.assertGreaterEqual(items.count(), 8)
            self.assertGreaterEqual(items.values('category').distinct().count(), 8)

    def test_anonymous_and_unauthorized_users_are_denied(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.simulation_data()).status_code, 403)
        self.assertFalse(TestRun.objects.exists())

    def test_voip_is_removed_and_old_url_is_rejected(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertNotContains(response, 'VoIP')
        self.assertContains(response, 'مدیریت پیام‌رسانی')
        self.assertEqual(self.client.get(self.url, {'channel': 'voip'}).status_code, 400)

    def test_each_section_renders_independently(self):
        self.client.force_login(self.admin)
        expected = {'configuration': 'id="configuration-form"', 'templates': 'id="template-form"',
                    'test': 'id="simulation-form"', 'history': 'سابقه آزمایش‌های'}
        for section, marker in expected.items():
            response = self.client.get(self.url, {'section': section})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, marker)

    def test_configuration_save_is_persistent_and_channel_scoped(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url + '?channel=sms&section=configuration', self.config_data())
        self.assertEqual(response.status_code, 302)
        config = ChannelConfiguration.objects.get(channel='sms')
        self.assertEqual(config.connection['endpoint'], 'https://example.com/api')
        self.assertEqual(config.updated_by, self.admin)
        self.assertFalse(ChannelConfiguration.objects.filter(channel='email').exists())

    def test_manager_can_test_but_cannot_change_configuration_or_templates(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(self.url, self.config_data()).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.template_data()).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.simulation_data()).status_code, 302)
        self.assertEqual(TestRun.objects.get().requested_by, self.manager)

    def test_custom_template_can_be_created_and_edited(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url + '?channel=sms&section=templates', self.template_data())
        self.assertEqual(response.status_code, 302)
        item = MessageTemplate.objects.get(channel='sms', name='قالب اختصاصی')
        self.assertEqual(item.created_by, self.admin)
        response = self.client.post(self.url + f'?channel=sms&section=templates&edit={item.pk}',
                                    self.template_data(**{'template-body': 'متن ویرایش‌شده {date}'}))
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.body, 'متن ویرایش‌شده {date}')
        self.assertEqual(item.updated_by, self.admin)

    def test_template_validation_rejects_unknown_variables_and_duplicate_names(self):
        for text in ('{unknown}', '{{customer_name}}', '{customer_name.__class__}'):
            form = MessageTemplateForm(self.template_data(**{'template-body': text}), channel='sms', prefix='template')
            self.assertFalse(form.is_valid())
            self.assertIn('body', form.errors)
        existing = MessageTemplate.objects.filter(channel='sms').first()
        form = MessageTemplateForm(self.template_data(**{'template-name': existing.name}), channel='sms', prefix='template')
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_simulation_uses_selected_template_and_appends_custom_text_without_network(self):
        self.client.force_login(self.admin)
        self.sms_template.body = 'سلام {customer_name} از {company_name}'
        self.sms_template.save(update_fields=['body'])
        with patch('socket.socket.connect', side_effect=AssertionError('network must not be used')):
            response = self.client.post(self.url + '?channel=sms&section=test', self.simulation_data())
        self.assertEqual(response.status_code, 302)
        run = TestRun.objects.get()
        self.assertEqual(run.template, self.sms_template)
        self.assertEqual(run.custom_text, 'متن دلخواه کاربر')
        self.assertTrue(run.rendered_text.endswith('متن دلخواه کاربر'))
        self.assertIn('<script>نام</script>', run.rendered_text)
        self.assertEqual(len(mail.outbox), 0)
        rendered = self.client.get(response.url)
        self.assertContains(rendered, '&lt;script&gt;نام&lt;/script&gt;')
        self.assertNotContains(rendered, '<script>نام</script>')

    def test_template_from_another_channel_cannot_be_simulated(self):
        self.client.force_login(self.admin)
        email_template = MessageTemplate.objects.filter(channel='email').first()
        response = self.client.post(self.url + '?channel=sms&section=test', self.simulation_data(email_template))
        self.assertEqual(response.status_code, 200)
        self.assertIn('template', response.context['simulation_form'].errors)
        self.assertFalse(TestRun.objects.exists())

    def test_custom_text_and_email_subject_limits_are_form_errors(self):
        self.client.force_login(self.admin)
        email_template = MessageTemplate.objects.filter(channel='email').first()
        email_template.subject = '{task_title} {task_title}'
        email_template.save(update_fields=['subject'])
        response = self.client.post(self.url + '?channel=email&section=test', self.simulation_data(
            email_template, **{'simulation-recipient': 'test@example.com', 'simulation-task_title': 'x' * 150}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['simulation_form'].non_field_errors())
        self.assertFalse(TestRun.objects.exists())

    def test_advanced_permissions_control_sections_and_actions(self):
        UserPermissionOverride.objects.create(user=self.manager, permission_key='communications.templates', granted=False)
        UserPermissionOverride.objects.create(user=self.manager, permission_key='communications.history', granted=False)
        UserPermissionOverride.objects.create(user=self.manager, permission_key='communications.test', granted=False)
        self.client.force_login(self.manager)
        response = self.client.get(self.url, {'section': 'templates'})
        self.assertEqual(response.context['section'], 'configuration')
        self.assertNotContains(response, 'section=templates')
        self.assertEqual(self.client.post(self.url, self.simulation_data()).status_code, 403)

    def test_explicit_permissions_can_open_only_selected_tab(self):
        for key in ('communications.view', 'communications.templates'):
            UserPermissionOverride.objects.create(user=self.outsider, permission_key=key, granted=True)
        self.client.force_login(self.outsider)
        response = self.client.get(self.url, {'section': 'templates'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['allowed_sections'], ['templates'])
        self.assertNotContains(response, 'section=configuration')

    def test_history_filters_and_paginates_at_ten(self):
        self.client.force_login(self.admin)
        for index in range(13):
            TestRun.objects.create(channel='sms', kind='message', status='simulated', recipient=f'091200000{index:02d}',
                                   result='تست', requested_by=self.admin, template=self.sms_template)
        other = TestRun.objects.create(channel='email', kind='message', status='simulated', result='تست ایمیل')
        response = self.client.get(self.url, {'section': 'history'})
        self.assertEqual(len(response.context['page_obj']), 10)
        self.assertEqual(response.context['page_obj'].paginator.count, 13)
        self.assertEqual(len(self.client.get(self.url, {'section': 'history', 'page': 2}).context['page_obj']), 3)
        self.assertIsNone(self.client.get(self.url, {'section': 'test', 'run': other.pk}).context['selected_run'])

    def test_history_has_no_delete_action_and_admin_delete_is_superuser_only(self):
        run = TestRun.objects.create(channel='sms', kind='message', status='simulated', result='تست')
        self.client.force_login(self.admin)
        response = self.client.get(self.url, {'section': 'history'})
        self.assertNotContains(response, f'/delete/{run.pk}')
        model_admin = TestRunAdmin(TestRun, admin.site)
        factory = RequestFactory()
        request = factory.get('/admin/')
        request.user = self.manager
        self.assertFalse(model_admin.has_delete_permission(request, run))
        request.user = self.admin
        self.assertTrue(model_admin.has_delete_permission(request, run))

    def test_configuration_check_is_local_only(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, {'action': 'check'})
        self.assertEqual(TestRun.objects.get().status, 'incomplete')
        self.client.post(self.url, self.config_data())
        self.client.post(self.url, {'action': 'check'})
        latest = TestRun.objects.first()
        self.assertEqual(latest.status, 'simulated')
        self.assertIn('هنوز بررسی نشده‌اند', latest.result)

    def test_invalid_destination_stays_on_form_with_local_error(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url + '?section=test', self.simulation_data(**{'simulation-recipient': 'bad'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_simulation-recipient-errors"')
        self.assertFalse(TestRun.objects.exists())

    def test_unknown_action_is_rejected(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(self.url, {'action': 'send_live'}).status_code, 400)
        self.assertFalse(TestRun.objects.exists())
