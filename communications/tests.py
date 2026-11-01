from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserPermissionOverride
from accounts.permissions import ROLE_TO_GROUP
from .forms import ConfigurationForm, SimulationForm
from .models import ChannelConfiguration, TestRun
from .services import DEFAULT_TEMPLATE, render_message


class NotificationCenterTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('notice_admin', password='test-password')
        self.manager = User.objects.create_user('notice_manager', password='test-password')
        self.manager.groups.add(Group.objects.get_or_create(name=ROLE_TO_GROUP['sales_manager'])[0])
        self.outsider = User.objects.create_user('notice_other', password='test-password')
        self.url = reverse('communications:center')

    def config_data(self, **changes):
        data = {'action': 'save', 'config-provider': 'custom', 'config-sender': '1000123',
                'config-credential_env': 'SMS_API_KEY', 'config-endpoint': 'https://example.com/api',
                'config-message_template': 'سلام {customer_name}: {task_title} از {company_name} در {date} {time}'}
        data.update(changes)
        return data

    def simulation_data(self, **changes):
        data = {'action': 'simulate', 'simulation-recipient': '۰۹۱۲۳۴۵۶۷۸۹', 'simulation-sample_name': '<script>نام</script>',
                'simulation-company_name': 'دیجیران', 'simulation-task_title': 'پیگیری آزمایشی'}
        data.update(changes)
        return data

    def test_anonymous_and_unauthorized_denied(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.outsider)
        for method, data in [('get', {}), ('post', self.simulation_data()), ('post', self.config_data())]:
            self.assertEqual(getattr(self.client, method)(self.url, data).status_code, 403)
        self.assertFalse(TestRun.objects.exists())
        self.assertFalse(ChannelConfiguration.objects.exists())

    def test_get_is_read_only_and_all_channels_render(self):
        self.client.force_login(self.admin)
        for channel in ('sms', 'email', 'whatsapp', 'voip'):
            response = self.client.get(self.url, {'channel': channel})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'محیط آزمایش')
            self.assertContains(response, 'id="configuration-form"')
            self.assertContains(response, 'id="simulation-form"')
        self.assertFalse(ChannelConfiguration.objects.exists())
        self.assertFalse(TestRun.objects.exists())

    def test_configuration_save_is_persistent_and_channel_scoped(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url + '?channel=sms', self.config_data())
        self.assertEqual(response.status_code, 302)
        config = ChannelConfiguration.objects.get()
        self.assertEqual(config.channel, 'sms')
        self.assertEqual(config.connection['endpoint'], 'https://example.com/api')
        self.assertEqual(config.updated_by, self.admin)
        response = self.client.get(self.url + '?channel=email')
        self.assertEqual(response.context['configuration'].provider, 'pending')
        self.assertEqual(ChannelConfiguration.objects.count(), 1)

    def test_manager_can_simulate_but_cannot_change_configuration(self):
        self.client.force_login(self.manager)
        response = self.client.get(self.url)
        self.assertFalse(response.context['can_manage'])
        self.assertTrue(all(field.disabled for field in response.context['config_form'].fields.values()))
        self.assertEqual(self.client.post(self.url, self.config_data()).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.simulation_data()).status_code, 302)
        self.assertFalse(ChannelConfiguration.objects.exists())
        self.assertEqual(TestRun.objects.get().requested_by, self.manager)

    def test_advanced_permission_denial_and_grant_apply(self):
        UserPermissionOverride.objects.create(user=self.manager, permission_key='communications.test', granted=False)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(self.url, self.simulation_data()).status_code, 403)
        for key in ('communications.view', 'communications.test'):
            UserPermissionOverride.objects.create(user=self.outsider, permission_key=key, granted=True)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.post(self.url, self.simulation_data()).status_code, 302)
        self.assertEqual(self.client.post(self.url, self.config_data()).status_code, 403)

    def test_simulation_does_not_send_or_connect_and_escapes_output(self):
        self.client.force_login(self.admin)
        with patch('socket.socket.connect', side_effect=AssertionError('Outbound connection is forbidden in simulation')):
            response = self.client.post(self.url, self.simulation_data())
        self.assertEqual(response.status_code, 302)
        run = TestRun.objects.get()
        self.assertEqual(run.recipient, '09123456789')
        self.assertEqual(run.status, 'simulated')
        self.assertIn('<script>نام</script>', run.rendered_text)
        self.assertNotIn('{customer_name}', run.rendered_text)
        self.assertEqual(len(mail.outbox), 0)
        response = self.client.get(response.url)
        self.assertContains(response, '&lt;script&gt;نام&lt;/script&gt;')
        self.assertNotContains(response, '<script>نام</script>')
        self.assertEqual(TestRun.objects.count(), 1)

    def test_configuration_check_never_reports_live_connection(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, {'action': 'check'})
        run = TestRun.objects.get()
        self.assertEqual(run.status, 'incomplete')
        self.assertIn('انتخاب سرویس', run.result)
        self.client.post(self.url, self.config_data())
        self.client.post(self.url, {'action': 'check'})
        run = TestRun.objects.first()
        self.assertEqual(run.status, 'simulated')
        self.assertIn('هنوز بررسی نشده‌اند', run.result)

    def test_unknown_placeholders_and_raw_credentials_are_rejected(self):
        for text in ('{customer_name.__class__}', '{{customer_name}}', '{unknown}', '{customer_name[0]}'):
            form = ConfigurationForm(self.config_data(**{'config-message_template': text}), channel='sms', prefix='config')
            self.assertFalse(form.is_valid())
            self.assertIn('message_template', form.errors)
        form = ConfigurationForm(self.config_data(**{'config-credential_env': 'a-secret-1234'}), channel='sms', prefix='config')
        self.assertFalse(form.is_valid())
        self.assertIn('credential_env', form.errors)

    def test_destination_validation_for_each_channel(self):
        for channel, recipient in [('sms', '1234'), ('whatsapp', 'bad'), ('email', 'bad'), ('voip', '+abc')]:
            form = SimulationForm(self.simulation_data(**{'simulation-recipient': recipient}), channel=channel, prefix='simulation')
            self.assertFalse(form.is_valid())
            self.assertIn('recipient', form.errors)
        form = SimulationForm(self.simulation_data(**{'simulation-recipient': '1234'}), channel='voip', prefix='simulation')
        self.assertTrue(form.is_valid(), form.errors)

    def test_history_filters_pagination_and_cross_channel_isolation(self):
        self.client.force_login(self.admin)
        for i in range(13):
            TestRun.objects.create(channel='sms', kind='message', status='simulated', recipient='09123456789', result='تست', requested_by=self.admin)
        other = TestRun.objects.create(channel='email', kind='message', status='simulated', result='تست ایمیل')
        response = self.client.get(self.url)
        self.assertEqual(len(response.context['page_obj']), 10)
        self.assertEqual(response.context['page_obj'].paginator.count, 13)
        self.assertEqual(len(self.client.get(self.url, {'page': 2}).context['page_obj']), 3)
        self.assertIsNone(self.client.get(self.url, {'run': other.pk}).context['selected_run'])
        self.assertEqual(self.client.get(self.url, {'status': 'incomplete'}).context['page_obj'].paginator.count, 0)
        self.assertEqual(self.client.get(self.url, {'q': 'no-match'}).context['page_obj'].paginator.count, 0)
        self.assertFalse(self.client.get(self.url, {'date_from': 'bad'}).context['filters'].is_valid())

    def test_invalid_post_keeps_field_error_and_values(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, self.simulation_data(**{'simulation-recipient': 'bad'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_simulation-recipient-errors"')
        self.assertContains(response, 'value="bad"')
        self.assertFalse(TestRun.objects.exists())

    def test_unknown_channel_and_action_are_rejected(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url + '?channel=unknown').status_code, 400)
        self.assertEqual(self.client.post(self.url, {'action': 'send_live'}).status_code, 400)
        self.assertFalse(TestRun.objects.exists())

    def test_expanded_email_subject_limit_is_a_form_error(self):
        ChannelConfiguration.objects.create(channel='email', message_template='سلام {customer_name}', subject='{task_title} {task_title}')
        self.client.force_login(self.admin)
        response = self.client.post(self.url + '?channel=email', self.simulation_data(**{'simulation-recipient': 'test@example.com', 'simulation-task_title': 'x' * 150}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['simulation_form'].non_field_errors())
        self.assertFalse(TestRun.objects.exists())

    def test_email_api_readiness_uses_endpoint_instead_of_smtp_host(self):
        from .services import configuration_gaps
        config = ChannelConfiguration(channel='email', provider='custom', sender='sender@example.com', credential_env='EMAIL_KEY', connection={'endpoint': 'https://example.com/api'})
        self.assertEqual(configuration_gaps(config), [])
        config.provider = 'smtp'
        self.assertIn('میزبان', configuration_gaps(config))
