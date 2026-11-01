from django.conf import settings
from django.db import models


class ChannelConfiguration(models.Model):
    CHANNELS = [('sms', 'پیامک'), ('email', 'ایمیل'), ('whatsapp', 'واتساپ'), ('voip', 'VoIP')]
    channel = models.CharField('کانال', max_length=16, choices=CHANNELS, unique=True)
    provider = models.CharField('سرویس پیشنهادی', max_length=40, blank=True)
    sender = models.CharField('فرستنده', max_length=160, blank=True)
    credential_env = models.CharField('نام متغیر اعتبار اتصال', max_length=100, blank=True)
    connection = models.JSONField('تنظیمات اتصال', default=dict, blank=True)
    subject = models.CharField('عنوان ایمیل', max_length=200, blank=True)
    message_template = models.TextField('قالب پیام', max_length=4000)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def updated_by_name(self):
        return (self.updated_by.get_full_name() or self.updated_by.username) if self.updated_by else 'کاربر حذف‌شده'

    def __str__(self):
        return self.get_channel_display()


class TestRun(models.Model):
    channel = models.CharField(max_length=16, choices=ChannelConfiguration.CHANNELS)
    kind = models.CharField(max_length=16, choices=[('message', 'تست پیام'), ('configuration', 'بررسی تنظیمات')])
    status = models.CharField(max_length=16, choices=[('simulated', 'شبیه‌سازی شد'), ('incomplete', 'نیاز به تکمیل')])
    recipient = models.CharField('مقصد آزمایش', max_length=254, blank=True)
    subject = models.CharField(max_length=200, blank=True)
    rendered_text = models.TextField(max_length=5000, blank=True)
    result = models.TextField()
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def actor_name(self):
        return (self.requested_by.get_full_name() or self.requested_by.username) if self.requested_by else 'کاربر حذف‌شده'

    class Meta:
        ordering = ['-created_at', '-pk']
        indexes = [models.Index(fields=['channel', '-created_at'])]
