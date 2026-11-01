from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from accounts.permissions import has_permission, require_permission, _handle_denied
from crm.pagination import paginate
from crm.numerals import digit_contains
from .forms import ConfigurationForm, LogFilterForm, SimulationForm
from .models import ChannelConfiguration, TestRun
from .services import DEFAULT_TEMPLATE, VARIABLES, configuration_gaps, render_message, sample_values


@require_permission('communications.view')
@require_http_methods(['GET', 'POST'])
def center(request):
    channel = request.GET.get('channel', 'sms')
    if channel not in dict(ChannelConfiguration.CHANNELS):
        return HttpResponseBadRequest('کانال اعلان معتبر نیست.')
    config = ChannelConfiguration.objects.filter(channel=channel).first() or ChannelConfiguration(
        channel=channel, provider='pending', message_template=DEFAULT_TEMPLATE, subject='یادآوری {task_title}' if channel == 'email' else '')
    action = request.POST.get('action') if request.method == 'POST' else None
    if action and action not in ('save', 'simulate', 'check'):
        return HttpResponseBadRequest('عملیات معتبر نیست.')
    if request.method == 'POST' and not action:
        return HttpResponseBadRequest('عملیات را مشخص کنید.')
    if action:
        permission = 'communications.manage' if action == 'save' else 'communications.test'
        if not has_permission(request.user, permission):
            return _handle_denied(request, permission, '403', 'dashboard:home')
    config_form = ConfigurationForm(request.POST if action == 'save' else None, instance=config, channel=channel, prefix='config')
    simulation_form = SimulationForm(request.POST if action == 'simulate' else None, channel=channel, prefix='simulation')
    if action == 'save' and config_form.is_valid():
        config = config_form.save(commit=False)
        config, _ = ChannelConfiguration.objects.update_or_create(channel=channel, defaults={
            'provider': config.provider, 'sender': config.sender, 'credential_env': config.credential_env,
            'connection': config.connection, 'subject': config.subject, 'message_template': config.message_template, 'updated_by': request.user})
        request.feedback_context = {'form': '#configuration-form'}
        messages.success(request, 'تنظیمات و قالب ذخیره شد؛ حالت شبیه‌سازی برقرار است.')
        return redirect(reverse('communications:center') + '?' + urlencode({'channel': channel}) + '#configuration')
    if action == 'simulate' and simulation_form.is_valid():
        values = sample_values(simulation_form.cleaned_data)
        try:
            body = render_message(config.message_template, values)
            subject = render_message(config.subject, values)
            if len(subject) > 200 or len(body) > 5000:
                raise ValidationError('متن نهایی بیش از حد طولانی است؛ قالب یا داده‌های نمونه را کوتاه‌تر کنید.')
        except ValidationError as error:
            simulation_form.add_error(None, error)
        else:
            run = TestRun.objects.create(channel=channel, kind='message', status='simulated', recipient=simulation_form.cleaned_data['recipient'],
                subject=subject, rendered_text=body, requested_by=request.user,
                result='متن با داده نمونه آماده و ثبت شد. هیچ پیام، ایمیل یا تماس واقعی ارسال نشد.')
            request.feedback_context = {'form': '#simulation-result'}
            messages.success(request, 'شبیه‌سازی انجام شد. نتیجه و متن نهایی را در همین بخش ببینید.')
            return redirect(reverse('communications:center') + '?' + urlencode({'channel': channel, 'run': run.pk}) + '#simulation-result')
    if action == 'check':
        gaps = configuration_gaps(config)
        run = TestRun.objects.create(channel=channel, kind='configuration', status='incomplete' if gaps else 'simulated', requested_by=request.user,
            result=('موارد تکمیل‌نشده: ' + '، '.join(gaps) + '. ' if gaps else 'تنظیمات پیشنهادی ثبت شده‌اند. ') + 'اتصال، اعتبار کلید و دسترسی سرویس واقعی هنوز بررسی نشده‌اند.')
        request.feedback_context = {'form': '#simulation-result'}
        messages.info(request, 'بررسی محلی تنظیمات ثبت شد؛ نتیجه در همین بخش نمایش داده می‌شود.')
        return redirect(reverse('communications:center') + '?' + urlencode({'channel': channel, 'run': run.pk}) + '#simulation-result')
    can_manage = has_permission(request.user, 'communications.manage')
    if not can_manage:
        for field in config_form.fields.values():
            field.disabled = True
    logs = TestRun.objects.filter(channel=channel).select_related('requested_by')
    filters = LogFilterForm(request.GET)
    if filters.is_valid():
        data = filters.cleaned_data
        if data['q']:
            logs = logs.filter(digit_contains('recipient', data['q']) | Q(rendered_text__icontains=data['q']) | Q(result__icontains=data['q']) | Q(requested_by__username__icontains=data['q']))
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
    if request.GET.get('run', '').isascii() and request.GET.get('run', '').isdigit():
        selected = TestRun.objects.filter(pk=request.GET['run'], channel=channel).select_related('requested_by').first()
    channels = []
    configs = {item.channel: item for item in ChannelConfiguration.objects.all()}
    for key, title in ChannelConfiguration.CHANNELS:
        item = configs.get(key)
        channels.append({'key': key, 'title': title, 'saved': bool(item), 'complete': bool(item and not configuration_gaps(item))})
    return render(request, 'communications/center.html', {'channel': channel, 'channel_title': dict(ChannelConfiguration.CHANNELS)[channel],
        'channels': channels, 'configuration': config, 'config_form': config_form, 'simulation_form': simulation_form,
        'can_manage': can_manage, 'can_test': has_permission(request.user, 'communications.test'), 'variables': list(VARIABLES.items()),
        'filters': filters, 'page_obj': paginate(request, logs), 'selected_run': selected,
        'preview_template': config.message_template, 'preview_subject': config.subject})
