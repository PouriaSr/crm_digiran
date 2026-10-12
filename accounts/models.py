from django.contrib.auth.models import User
from django.db import models


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