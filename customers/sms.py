"""Customer-facing SMS workflows backed by the configured messaging service."""
from dataclasses import dataclass
import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from communications.models import ChannelConfiguration, MessageTemplate, TestRun
from communications.services import ProviderConnectionError, render_message, send_melipayamak
from dashboard.templatetags.fa_numbers import jdate

logger = logging.getLogger('crm.sms')


@dataclass(frozen=True)
class SmsDeliveryResult:
    sent: bool
    message: str
    reference: str = ''

    def __bool__(self):
        return self.sent


def _address_values(customer, requested_by=None):
    now = timezone.localtime()
    company = getattr(settings, 'COMPANY_INFO', {})
    expert = customer.assigned_to or requested_by
    expert_name = (expert.get_full_name() or expert.username) if expert else ''
    return {
        'customer_name': customer.name,
        'customer_mobile': customer.mobile,
        'company_name': company.get('name', 'دیجیران'),
        'expert_name': expert_name,
        'task_title': 'ارسال آدرس',
        'contract_number': '',
        'amount': '',
        'due_date': '',
        'address': company.get('address', ''),
        'date': jdate(now, 'Y/m/d'),
        'time': now.strftime('%H:%M'),
    }


def send_address_sms(customer, *, requested_by=None, request_token=''):
    """Render and send the active ``ارسال آدرس`` template to one customer."""
    if request_token:
        previous = TestRun.objects.filter(request_token=request_token).first()
        if previous:
            return SmsDeliveryResult(
                previous.status == 'sent', previous.result, previous.provider_reference,
            )

    template = MessageTemplate.objects.filter(
        channel='sms', name='ارسال آدرس', is_active=True,
    ).first()
    config = ChannelConfiguration.objects.filter(channel='sms').first()
    if not template:
        message = 'قالب فعال «ارسال آدرس» پیدا نشد.'
        TestRun.objects.create(
            channel='sms', kind='live', status='incomplete', recipient=customer.mobile,
            requested_by=requested_by, request_token=request_token or None, result=message,
        )
        return SmsDeliveryResult(False, message)
    if not config or config.provider != 'melipayamak':
        message = 'پیکربندی فعال ملی‌پیامک پیدا نشد.'
        TestRun.objects.create(
            channel='sms', kind='live', status='incomplete', recipient=customer.mobile,
            requested_by=requested_by, request_token=request_token or None,
            template=template, result=message,
        )
        return SmsDeliveryResult(False, message)

    try:
        body = render_message(template.body, _address_values(customer, requested_by))
    except ValidationError as error:
        message = f'قالب «ارسال آدرس» معتبر نیست: {error.messages[0]}'
        TestRun.objects.create(
            channel='sms', kind='live', status='incomplete', recipient=customer.mobile,
            requested_by=requested_by, request_token=request_token or None,
            template=template, result=message,
        )
        return SmsDeliveryResult(False, message)
    run = TestRun.objects.create(
        channel='sms', kind='live', status='incomplete', recipient=customer.mobile,
        rendered_text=body, template=template, requested_by=requested_by,
        request_token=request_token or None, result='درخواست ارسال آدرس در حال پردازش است.',
    )
    try:
        reference = send_melipayamak(config, customer.mobile, body)
    except ProviderConnectionError as error:
        run.result = f'ارسال آدرس انجام نشد: {error}'
        run.save(update_fields=['result'])
        logger.warning('Address SMS failed safely, customer_id=%s run_id=%s', customer.pk, run.pk)
        return SmsDeliveryResult(False, run.result)

    run.status = 'sent'
    run.provider_reference = reference
    run.result = 'پیامک آدرس با موفقیت به سرویس ملی‌پیامک تحویل شد.'
    run.save(update_fields=['status', 'provider_reference', 'result'])
    logger.info('Address SMS sent, customer_id=%s run_id=%s', customer.pk, run.pk)
    return SmsDeliveryResult(True, run.result, reference)
