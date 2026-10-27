"""Address SMS test hook. No provider or network call is configured yet."""
import logging

logger = logging.getLogger('crm.sms')


def send_address_sms(customer):
    """Record a test request only; False means no real SMS was sent."""
    logger.info('Address SMS requested (TEST ONLY; NOT SENT), customer_id=%s', customer.pk)
    return False
