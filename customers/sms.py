"""
هوک پیامک خودکار مرکز مشتریان.

هر وقت API پنل پیامکی مشخص شد، فقط بدنه‌ی این تابع را پر کنید؛
بقیه‌ی سیستم از قبل به آن وصل است.
"""
import logging

logger = logging.getLogger('crm.sms')


def send_followup_sms(customer, message=None):
    """
    پیامک خودکار وقتی «نیاز به پیگیری» تیک می‌خورد.

    Returns:
        bool: True اگر پیامک واقعاً ارسال شد.
    """
    text = message or (
        f'{customer.name} عزیز، درخواست پیگیری شما ثبت شد. '
        'همکاران ما به‌زودی با شما تماس می‌گیرند.'
    )
    logger.info('SMS (pending API) → %s | %s', customer.mobile, text)
    # TODO: اتصال به API پنل پیامکی
    # requests.post(SMS_API_URL, data={...}, timeout=10).raise_for_status()
    return False
