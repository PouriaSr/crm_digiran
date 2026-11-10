from django.contrib.auth.models import User
from django.db import models


class UserRoleProfile(models.Model):
    """An optional display title; authorization always uses the base role."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='role_profile')
    display_name = models.CharField('عنوان دلخواه نقش', max_length=100, blank=True)

    def __str__(self):
        return f'{self.user.username} — {self.display_name}'


class UserPermissionOverride(models.Model):
    """بازنویسی دسترسی کاربر — فراتر از نقش"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='permission_overrides',
        verbose_name='کاربر',
    )
    permission_key = models.CharField('کلید دسترسی', max_length=100)
    granted = models.BooleanField(
        'داده شده',
        help_text='True=دسترسی داده شده، False=دسترسی سلب شده',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'بازنویسی دسترسی'
        verbose_name_plural = 'بازنویسی‌های دسترسی'
        unique_together = [('user', 'permission_key')]
        ordering = ['user__username', 'permission_key']

    def __str__(self):
        status = '✓' if self.granted else '✗'
        return f'{self.user.username} — {self.permission_key} {status}'


class InterfaceComponent(models.Model):
    """Overrides for registered UI parts and custom internal links/content pages."""
    key = models.CharField('شناسه', max_length=180, unique=True)
    kind = models.CharField('نوع', max_length=20)
    section = models.CharField('بخش', max_length=100, blank=True)
    label = models.CharField('عنوان', max_length=180, blank=True)
    enabled = models.BooleanField('نمایش داده شود', default=True)
    position = models.IntegerField('ترتیب', default=100)
    roles = models.JSONField('نقش‌های مجاز', default=list, blank=True)
    permission = models.CharField('مجوز لازم', max_length=100, blank=True)
    url = models.CharField('مسیر داخلی', max_length=500, blank=True)
    scope_path = models.CharField('نمایش در مسیر', max_length=200, blank=True)
    body = models.TextField('محتوا', blank=True)
    custom = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=1)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['section', 'position', 'pk']
        verbose_name = 'جزء رابط سیستم'
        verbose_name_plural = 'اجزای رابط سیستم'

    def __str__(self):
        return self.label or self.key


class InterfaceChange(models.Model):
    key = models.CharField(max_length=180)
    action = models.CharField(max_length=20)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-pk']
