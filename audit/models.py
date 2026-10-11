from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AuditLog(models.Model):
    """لاگ سیستم — ثبت خودکار همه‌ی تغییرات مدل‌های حساس (۸.۴)"""

    ACTION_CREATED = 'created'
    ACTION_UPDATED = 'updated'
    ACTION_DELETED = 'deleted'

    ACTION_CHOICES = [
        (ACTION_CREATED, 'ایجاد'),
        (ACTION_UPDATED, 'ویرایش'),
        (ACTION_DELETED, 'حذف'),
    ]

    ACTION_ICONS = {
        ACTION_CREATED: '➕',
        ACTION_UPDATED: '✏️',
        ACTION_DELETED: '🗑',
    }

    ACTION_COLORS = {
        ACTION_CREATED: 'green',
        ACTION_UPDATED: 'blue',
        ACTION_DELETED: 'red',
    }

    # ═══ اتصال generic به هر مدل ═══
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True,
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    # ═══ اسنپ‌شات ═══
    object_repr = models.CharField('نمایش شیء', max_length=255)
    model_name = models.CharField('نام مدل', max_length=100, db_index=True)
    verbose_name = models.CharField('نام نمایشی مدل', max_length=100)

    # ═══ اکشن ═══
    action = models.CharField(
        'رویداد', max_length=20, choices=ACTION_CHOICES, db_index=True,
    )

    # ═══ کاربر و متادیتا ═══
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audit_logs', verbose_name='کاربر',
    )
    changes = models.JSONField('تغییرات', default=dict, blank=True)
    description = models.TextField('توضیحات', blank=True)

    ip_address = models.GenericIPAddressField('IP', null=True, blank=True)
    user_agent = models.CharField('User-Agent', max_length=300, blank=True)

    created_at = models.DateTimeField('تاریخ ثبت', auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'لاگ سیستم'
        verbose_name_plural = 'لاگ‌های سیستم'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action', '-created_at']),
        ]

    def __str__(self):
        return f'{self.verbose_name} — {self.get_action_display()} — {self.created_at:%Y/%m/%d %H:%M}'

    @property
    def user_display(self):
        if not self.user:
            return 'سیستم'
        return self.user.get_full_name() or self.user.username

    @property
    def icon(self):
        return self.ACTION_ICONS.get(self.action, '•')

    @property
    def color(self):
        return self.ACTION_COLORS.get(self.action, 'gray')

    def changes_display(self):
        """لیست تغییرات برای نمایش در template"""
        if not self.changes:
            return []
        result = []
        for field, data in self.changes.items():
            result.append({
                'field': field,
                'label': data.get('label', field),
                'old': data.get('old', '—') or '—',
                'new': data.get('new', '—') or '—',
            })
        return result