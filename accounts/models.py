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
    scope_key = models.CharField(max_length=80,blank=True)
    body = models.TextField('محتوا', blank=True)
    custom = models.BooleanField(default=False)
    behavior = models.JSONField(default=dict,blank=True)
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


class SectionSchema(models.Model):
    key = models.SlugField(max_length=80, unique=True)
    label = models.CharField('نام بخش',max_length=120)
    custom = models.BooleanField(default=False)
    enabled = models.BooleanField('فعال',default=True)
    roles = models.JSONField(default=list,blank=True)
    permission = models.CharField(max_length=100,blank=True)
    position = models.IntegerField('ترتیب نمایش بخش',default=100)
    page_size = models.PositiveSmallIntegerField('تعداد در هر صفحه',default=10)
    sort_source = models.CharField('مرتب‌سازی پیش‌فرض',max_length=100,blank=True)
    descending = models.BooleanField('نزولی',default=True)
    gate_save = models.BooleanField('تکمیل گردش‌کار قبل از ویرایش اصلی',default=False)
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):return self.label


class SectionField(models.Model):
    TYPES=[('text','متن کوتاه'),('longtext','متن بلند'),('integer','عدد صحیح'),('decimal','عدد اعشاری'),('date','تاریخ'),('boolean','بله/خیر'),('choice','انتخاب تک‌گزینه‌ای'),('email','ایمیل'),('url','نشانی وب')]
    section = models.ForeignKey(SectionSchema,on_delete=models.CASCADE,related_name='fields')
    key = models.SlugField(max_length=70)
    label = models.CharField('عنوان',max_length=120)
    field_type = models.CharField('نوع داده',max_length=20,choices=TYPES,default='text')
    native_name = models.CharField(max_length=100,blank=True)
    required = models.BooleanField('الزامی',default=False)
    enabled = models.BooleanField('فعال',default=True)
    readonly = models.BooleanField('فقط خواندنی',default=False)
    position = models.IntegerField('ترتیب',default=100)
    placeholder = models.CharField('متن راهنما در کادر',max_length=180,blank=True)
    help_text = models.TextField('راهنما',blank=True)
    default_value = models.CharField('مقدار پیش‌فرض',max_length=500,blank=True)
    choices = models.JSONField('گزینه‌ها',default=list,blank=True)
    minimum = models.DecimalField('حداقل عدد',max_digits=20,decimal_places=4,null=True,blank=True)
    maximum = models.DecimalField('حداکثر عدد',max_digits=20,decimal_places=4,null=True,blank=True)
    max_length = models.PositiveIntegerField('حداکثر طول متن',null=True,blank=True)
    roles = models.JSONField(default=list,blank=True)
    revision = models.PositiveIntegerField(default=1)
    class Meta:
        ordering=['position','pk']
        constraints=[models.UniqueConstraint(fields=['section','key'],name='unique_section_field')]


    def __str__(self):return self.label


class SectionColumn(models.Model):
    section = models.ForeignKey(SectionSchema,on_delete=models.CASCADE,related_name='columns')
    key = models.SlugField(max_length=70)
    component_key = models.CharField(max_length=180,blank=True)
    label = models.CharField('عنوان ستون',max_length=120)
    source = models.CharField('منبع داده',max_length=120)
    enabled = models.BooleanField('نمایش ستون',default=True)
    position = models.IntegerField('ترتیب',default=100)
    width = models.PositiveSmallIntegerField('عرض ستون (پیکسل)',default=140)
    align = models.CharField('چینش',max_length=10,default='center',choices=[('right','راست'),('center','وسط'),('left','چپ')])
    display = models.CharField('قالب نمایش',max_length=15,default='text',choices=[('text','متن'),('number','عدد'),('money','مبلغ'),('date','تاریخ'),('badge','برچسب')])
    wrap = models.BooleanField('شکستن متن بلند',default=True)
    filterable = models.BooleanField('قابل فیلتر',default=False)
    searchable = models.BooleanField('قابل جستجو',default=False)
    revision = models.PositiveIntegerField(default=1)
    class Meta:
        ordering=['position','pk']
        constraints=[models.UniqueConstraint(fields=['section','key'],name='unique_section_column')]


    def __str__(self):return self.label


class SectionStage(models.Model):
    section = models.ForeignKey(SectionSchema,on_delete=models.CASCADE,related_name='stages')
    label = models.CharField('نام مرحله',max_length=120)
    position = models.IntegerField('ترتیب',default=100)
    enabled = models.BooleanField('فعال',default=True)
    initial = models.BooleanField('مرحله شروع',default=False)
    status = models.CharField(max_length=20,choices=[('pending','در انتظار'),('in_progress','در حال انجام'),('follow_up','پیگیری'),('done','انجام شده')],default='pending')
    assignee_role = models.CharField('نقش مسئول',max_length=40,blank=True)
    assignee = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True)
    create_task = models.BooleanField('ساخت وظیفه و اعلان',default=False)
    required_fields = models.JSONField(default=list,blank=True)
    revision = models.PositiveIntegerField(default=1)
    class Meta: ordering=['position','pk']


    def __str__(self):return self.label


class SectionTransition(models.Model):
    section = models.ForeignKey(SectionSchema,on_delete=models.CASCADE,related_name='transitions')
    source = models.ForeignKey(SectionStage,on_delete=models.CASCADE,related_name='outgoing')
    target = models.ForeignKey(SectionStage,on_delete=models.CASCADE,related_name='incoming')
    label = models.CharField('عنوان اقدام',max_length=120)
    roles = models.JSONField(default=list,blank=True)
    require_note = models.BooleanField('توضیح اجباری',default=False)
    enabled = models.BooleanField('فعال',default=True)
    revision = models.PositiveIntegerField(default=1)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['source','target'],name='unique_structure_transition')]


    def __str__(self):return self.label


class SectionRecord(models.Model):
    section = models.ForeignKey(SectionSchema,on_delete=models.PROTECT,related_name='records')
    content_type = models.ForeignKey('contenttypes.ContentType',on_delete=models.PROTECT,null=True,blank=True)
    object_id = models.PositiveBigIntegerField(null=True,blank=True)
    owner = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True)
    title = models.CharField(max_length=200,blank=True)
    data = models.JSONField(default=dict,blank=True)
    stage = models.ForeignKey(SectionStage,on_delete=models.PROTECT,null=True,blank=True)
    revision = models.PositiveIntegerField(default=1)
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['section','content_type','object_id'],name='unique_section_native_record')]


class SectionRecordEvent(models.Model):
    record = models.ForeignKey(SectionRecord,on_delete=models.PROTECT,related_name='events')
    actor = models.ForeignKey(User,on_delete=models.SET_NULL,null=True)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['-pk']
