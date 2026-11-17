import secrets
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from accounts.permissions import _handle_denied, has_permission, require_permission
from crm.numerals import digit_contains
from crm.pagination import paginate
from .forms import ConfigurationForm, LogFilterForm, MessageTemplateForm, SimulationForm, TemplateFilterForm
from .models import ChannelConfiguration, MessageTemplate, TestRun
from .services import (DEFAULT_TEMPLATE, VARIABLES, ProviderConnectionError, configuration_gaps,
                       render_message, sample_values, send_melipayamak, verify_melipayamak)


SECTION_PERMISSIONS = {
    'configuration': 'communications.configuration',
    'templates': 'communications.templates',
    'test': 'communications.test',
    'history': 'communications.history',
}


def _url(channel, section, **params):
    return reverse('communications:center') + '?' + urlencode({'channel': channel, 'section': section, **params})


@require_permission('communications.view')
@require_http_methods(['GET', 'POST'])
def center(request):
    channels_map = dict(ChannelConfiguration.CHANNELS)
    channel = request.GET.get('channel', 'sms')
    if channel not in channels_map:
        return HttpResponseBadRequest('کانال پیام‌رسانی معتبر نیست.')

    allowed_sections = [key for key, permission in SECTION_PERMISSIONS.items() if has_permission(request.user, permission)]
    if not allowed_sections:
        return _handle_denied(request, 'communications.view', '403', 'dashboard:home')
    requested_section = request.GET.get('section', allowed_sections[0])
    section = requested_section if requested_section in allowed_sections else allowed_sections[0]

    config = ChannelConfiguration.objects.filter(channel=channel).first() or ChannelConfiguration(
        channel=channel, provider='pending', message_template=DEFAULT_TEMPLATE,
    )
    action = request.POST.get('action') if request.method == 'POST' else None
    action_permissions = {
        'save_configuration': 'communications.manage',
        'save_template': 'communications.manage_templates',
        'simulate': 'communications.test',
        'send_live': 'communications.send_live',
        'check': 'communications.test',
    }
    if request.method == 'POST' and action not in action_permissions:
        return HttpResponseBadRequest('عملیات معتبر نیست.')
    if action and not has_permission(request.user, action_permissions[action]):
        return _handle_denied(request, action_permissions[action], '403', 'dashboard:home')
    action_section = {'save_configuration': 'configuration', 'save_template': 'templates', 'simulate': 'test',
                      'send_live': 'test', 'check': 'test'}.get(action)
    if action_section and action_section not in allowed_sections:
        return _handle_denied(request, SECTION_PERMISSIONS[action_section], '403', 'dashboard:home')

    edit_id = request.GET.get('edit', '')
    editing_template = None
    if edit_id.isascii() and edit_id.isdigit():
        editing_template = MessageTemplate.objects.filter(pk=edit_id, channel=channel).first()
        if not editing_template:
            return HttpResponseBadRequest('قالب انتخاب‌شده معتبر نیست.')

    config_form = ConfigurationForm(request.POST if action == 'save_configuration' else None,
                                    instance=config, channel=channel, prefix='config')
    template_form = MessageTemplateForm(request.POST if action == 'save_template' else None,
                                        instance=editing_template, channel=channel, prefix='template')
    simulation_form = SimulationForm(request.POST if action in ('simulate', 'send_live') else None,
                                     channel=channel, prefix='simulation')

    if action == 'save_configuration' and config_form.is_valid():
        saved = config_form.save(commit=False)
        config, _ = ChannelConfiguration.objects.update_or_create(channel=channel, defaults={
            'provider': saved.provider, 'sender': saved.sender, 'credential_env': saved.credential_env,
            'connection': saved.connection, 'message_template': config.message_template or DEFAULT_TEMPLATE,
            'updated_by': request.user,
        })
        request.feedback_context = {'form': '#configuration-form'}
        messages.success(request, 'پیکربندی کانال ذخیره شد؛ برای اطمینان «بررسی اتصال» را اجرا کنید.')
        return redirect(_url(channel, 'configuration') + '#configuration-form')

    if action == 'save_template' and template_form.is_valid():
        item = template_form.save(commit=False)
        if not item.pk:
            item.created_by = request.user
        item.updated_by = request.user
        item.save()
        request.feedback_context = {'form': '#template-form'}
        messages.success(request, 'قالب پیام ذخیره شد و اکنون در بخش آزمایش قابل انتخاب است.')
        return redirect(_url(channel, 'templates', edit=item.pk) + '#template-form')

    if action in ('simulate', 'send_live') and simulation_form.is_valid():
        item = simulation_form.cleaned_data['template']
        values = sample_values(simulation_form.cleaned_data)
        try:
            body = render_message(item.body, values)
            custom_text = simulation_form.cleaned_data['custom_text'].strip()
            if custom_text:
                body = body.rstrip() + '\n\n' + custom_text
            subject = render_message(item.subject, values)
            if len(subject) > 200 or len(body) > 5000:
                raise ValidationError('متن نهایی بیش از حد طولانی است؛ قالب یا متن دلخواه را کوتاه‌تر کنید.')
        except ValidationError as error:
            simulation_form.add_error(None, error)
        else:
            is_live = action == 'send_live'
            reference = ''
            if is_live:
                if channel != 'sms':
                    simulation_form.add_error(None, 'ارسال واقعی فعلاً فقط برای پیامک ملی‌پیامک فعال است.')
                else:
                    request_token = request.POST.get('live_send_token', '')
                    if len(request_token) < 24 or len(request_token) > 64 or not request_token.isascii():
                        return HttpResponseBadRequest('شناسه ارسال معتبر نیست؛ صفحه را تازه‌سازی کنید.')
                    previous = TestRun.objects.filter(request_token=request_token).first()
                    if previous:
                        messages.info(request, 'این درخواست قبلاً پردازش شده است و دوباره ارسال نشد.')
                        return redirect(_url(channel, 'test', run=previous.pk) + '#simulation-result')
                    run = TestRun.objects.create(
                        channel=channel, kind='live', status='incomplete',
                        recipient=simulation_form.cleaned_data['recipient'], subject=subject,
                        rendered_text=body, custom_text=custom_text, template=item, requested_by=request.user,
                        request_token=request_token, result='درخواست ارسال در حال پردازش است.',
                    )
                    try:
                        reference = send_melipayamak(config, simulation_form.cleaned_data['recipient'], body)
                    except ProviderConnectionError as error:
                        run.result = f'ارسال انجام نشد: {error}'
                        run.save(update_fields=['result'])
                        messages.error(request, 'ارسال پیامک انجام نشد؛ جزئیات امن خطا ثبت شد.')
                        return redirect(_url(channel, 'test', run=run.pk) + '#simulation-result')
            if not simulation_form.errors:
                if is_live:
                    run.status = 'sent'
                    run.provider_reference = reference
                    run.result = 'پیامک واقعی با موفقیت به سرویس ملی‌پیامک تحویل شد.'
                    run.save(update_fields=['status', 'provider_reference', 'result'])
                else:
                    run = TestRun.objects.create(
                        channel=channel, kind='message', status='simulated',
                        recipient=simulation_form.cleaned_data['recipient'], subject=subject,
                        rendered_text=body, custom_text=custom_text, template=item, requested_by=request.user,
                        result='پیش‌نمایش نهایی آماده و ثبت شد. هیچ پیامی ارسال نشد.',
                    )
                request.feedback_context = {'form': '#simulation-form'}
                messages.success(request, 'پیامک واقعی ارسال شد.' if is_live else 'پیش‌نمایش پیام ثبت شد؛ چیزی ارسال نشد.')
                return redirect(_url(channel, 'test', run=run.pk) + '#simulation-result')

    if action == 'check':
        gaps = configuration_gaps(config)
        status = 'incomplete' if gaps else 'simulated'
        if gaps:
            result = 'موارد تکمیل‌نشده: ' + '، '.join(gaps) + '.'
        elif channel == 'sms' and config.provider == 'melipayamak':
            try:
                verify_melipayamak(config)
            except ProviderConnectionError as error:
                result = f'اتصال ملی‌پیامک تأیید نشد: {error}'
                status = 'incomplete'
            else:
                result = 'ساختار امن نشانی ارسال ساده و خط فرستنده تأیید شد. هیچ پیامکی ارسال نشد؛ ارتباط واقعی هنگام ارسال آزمایشی کنترل می‌شود.'
                status = 'verified'
        else:
            result = 'پیکربندی پیشنهادی کامل است؛ اتصال واقعی این سرویس هنوز بررسی نشده است.'
        run = TestRun.objects.create(
            channel=channel, kind='configuration', status=status, requested_by=request.user, result=result,
        )
        messages.info(request, 'نتیجه بررسی پیکربندی ثبت شد؛ هیچ پیامی ارسال نشد.')
        return redirect(_url(channel, 'test', run=run.pk) + '#simulation-result')

    can_manage = has_permission(request.user, 'communications.manage')
    can_manage_templates = has_permission(request.user, 'communications.manage_templates')
    if not can_manage:
        for field in config_form.fields.values():
            field.disabled = True
    if not can_manage_templates:
        for field in template_form.fields.values():
            field.disabled = True

    template_filters = TemplateFilterForm(request.GET)
    templates = MessageTemplate.objects.filter(channel=channel).select_related('updated_by')
    if template_filters.is_valid():
        template_data = template_filters.cleaned_data
        if template_data['q']:
            templates = templates.filter(Q(name__icontains=template_data['q']) | Q(body__icontains=template_data['q']))
        if template_data['category']:
            templates = templates.filter(category=template_data['category'])
        if template_data['state']:
            templates = templates.filter(is_active=template_data['state'] == 'active')
    else:
        templates = templates.none()

    filters = LogFilterForm(request.GET)
    logs = TestRun.objects.filter(channel=channel).select_related('requested_by', 'template')
    if filters.is_valid():
        data = filters.cleaned_data
        if data['q']:
            logs = logs.filter(digit_contains('recipient', data['q']) | Q(rendered_text__icontains=data['q'])
                               | Q(result__icontains=data['q']) | Q(requested_by__username__icontains=data['q'])
                               | Q(template__name__icontains=data['q']))
        for key in ('status', 'kind'):
            if data[key]:
                logs = logs.filter(**{key: data[key]})
        if data['date_from']:
            logs = logs.filter(created_at__date__gte=data['date_from'])
        if data['date_to']:
            logs = logs.filter(created_at__date__lte=data['date_to'])
    else:
        logs = logs.none()

    selected = None
    run_id = request.GET.get('run', '')
    if run_id.isascii() and run_id.isdigit():
        selected = TestRun.objects.filter(pk=run_id, channel=channel).select_related('requested_by', 'template').first()

    configs = {item.channel: item for item in ChannelConfiguration.objects.filter(channel__in=channels_map)}
    channel_tabs = []
    for key, title in ChannelConfiguration.CHANNELS:
        item = configs.get(key)
        channel_tabs.append({'key': key, 'title': title, 'saved': bool(item),
                             'complete': bool(item and not configuration_gaps(item))})

    templates_for_test = list(MessageTemplate.objects.filter(channel=channel, is_active=True).values(
        'id', 'name', 'category', 'subject', 'body')) if section == 'test' else []
    return render(request, 'communications/center.html', {
        'channel': channel, 'channel_title': channels_map[channel], 'channels': channel_tabs,
        'section': section, 'allowed_sections': allowed_sections, 'configuration': config,
        'config_form': config_form, 'template_form': template_form, 'editing_template': editing_template,
        'simulation_form': simulation_form, 'can_manage': can_manage,
        'can_manage_templates': can_manage_templates, 'can_test': has_permission(request.user, 'communications.test'),
        'can_send_live': has_permission(request.user, 'communications.send_live'),
        'variables': list(VARIABLES.items()), 'template_filters': template_filters,
        'template_page': paginate(request, templates, key='template_page'),
        'filters': filters, 'page_obj': paginate(request, logs), 'selected_run': selected,
        'templates_json': templates_for_test, 'live_send_token': secrets.token_urlsafe(32),
    })
