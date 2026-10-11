"""
Signalهای Global Audit Log — فاز ۸.۴
"""
from datetime import date, datetime
from decimal import Decimal

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from crm.middleware import get_current_request, get_current_user
from .models import AuditLog
from .registry import AUDIT_MODELS


# ═══════════════════════════════════════════════════════════
# مقایسه‌ی امن مقادیر (type-agnostic)
# ═══════════════════════════════════════════════════════════
def _to_comparable(v):
    if v is None:
        return ''
    if isinstance(v, Decimal):
        return str(v.normalize())
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def _values_equal(a, b):
    return _to_comparable(a) == _to_comparable(b)


def _get_field_label(model, field_name):
    """label فارسی فیلد از verbose_name"""
    try:
        field = model._meta.get_field(field_name)
        return str(field.verbose_name)
    except Exception:
        return field_name


def _get_request_meta():
    """IP و User-Agent از request جاری"""
    request = get_current_request()
    if not request:
        return None, ''
    ip = (
        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or request.META.get('REMOTE_ADDR', '')
        or None
    )
    ua = (request.META.get('HTTP_USER_AGENT', '') or '')[:300]
    return ip, ua


def _create_log(instance, action, changes=None, description=''):
    """ساخت AuditLog با اطلاعات کامل"""
    model = instance.__class__
    ip, ua = _get_request_meta()
    user = get_current_user()

    try:
        ct = ContentType.objects.get_for_model(model)
    except Exception:
        ct = None

    AuditLog.objects.create(
        content_type=ct,
        object_id=instance.pk,
        object_repr=str(instance)[:255],
        model_name=f'{model._meta.app_label}.{model.__name__}',
        verbose_name=str(model._meta.verbose_name),
        action=action,
        user=user if (user and user.is_authenticated) else None,
        changes=changes or {},
        description=description,
        ip_address=ip,
        user_agent=ua,
    )


# ═══════════════════════════════════════════════════════════
# register_audit — اتصال signalها به یک مدل
# ═══════════════════════════════════════════════════════════
def register_audit(model, tracked_fields):
    """ثبت signalها برای یک مدل با فیلدهای مشخص"""

    @receiver(pre_save, sender=model, weak=False, dispatch_uid=f'audit_pre_{model._meta.label}')
    def capture_old(sender, instance, **kwargs):
        update_fields = kwargs.get('update_fields')
        # partial save که فقط فیلدهای غیر-tracked رو داره → skip
        if update_fields and not any(f in tracked_fields for f in update_fields):
            instance._audit_old = None
            return
        if not instance.pk:
            instance._audit_old = None
            return
        try:
            instance._audit_old = sender.objects.get(pk=instance.pk)
        except sender.DoesNotExist:
            instance._audit_old = None

    @receiver(post_save, sender=model, weak=False, dispatch_uid=f'audit_save_{model._meta.label}')
    def log_save(sender, instance, created, **kwargs):
        if created:
            _create_log(
                instance,
                AuditLog.ACTION_CREATED,
                description=f'{sender._meta.verbose_name} «{instance}» ایجاد شد.',
            )
            return

        old = getattr(instance, '_audit_old', None)
        if not old:
            return

        changes = {}
        for field in tracked_fields:
            old_val = getattr(old, field, None)
            new_val = getattr(instance, field, None)
            if not _values_equal(old_val, new_val):
                changes[field] = {
                    'label': _get_field_label(sender, field),
                    'old': _to_comparable(old_val),
                    'new': _to_comparable(new_val),
                }

        if not changes:
            return

        _create_log(
            instance,
            AuditLog.ACTION_UPDATED,
            changes=changes,
            description=f'{sender._meta.verbose_name} «{instance}» ویرایش شد.',
        )

    @receiver(post_delete, sender=model, weak=False, dispatch_uid=f'audit_delete_{model._meta.label}')
    def log_delete(sender, instance, **kwargs):
        _create_log(
            instance,
            AuditLog.ACTION_DELETED,
            description=f'{sender._meta.verbose_name} «{instance}» حذف شد.',
        )


# ═══════════════════════════════════════════════════════════
# فعال‌سازی خودکار برای همه‌ی مدل‌های رجیستری
# ═══════════════════════════════════════════════════════════
def _register_all():
    for model_label, fields in AUDIT_MODELS.items():
        try:
            app_label, model_name = model_label.split('.')
            model = apps.get_model(app_label, model_name)
            register_audit(model, fields)
        except LookupError:
            # مدل هنوز لود نشده — skip
            continue


_register_all()