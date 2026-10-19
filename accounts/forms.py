from collections import OrderedDict

from django import forms
from django.contrib.auth.models import User, Group
from crm.form_mixins import DuplicateCheckMixin


ROLE_CHOICES = [
    ('admin', 'مدیر کل'),
    ('sales_manager', 'مدیر فروش'),
    ('sales', 'کارشناس فروش'),
    ('support', 'پشتیبان'),
    ('accountant', 'حسابدار'),
    ('operator', 'اپراتور'),
    ('ads_manager', 'مسئول تبلیغات'),
    ('none', 'بدون نقش خاص'),
]

ROLE_GROUP_MAP = {
    'sales_manager': 'مدیر فروش',
    'sales': 'کارشناس فروش',
    'support': 'پشتیبان',
    'accountant': 'حسابدار',
    'operator': 'اپراتور',
    'ads_manager': 'مسئول تبلیغات',
}


def ensure_groups():
    for group_name in ROLE_GROUP_MAP.values():
        Group.objects.get_or_create(name=group_name)


def get_user_role(user):
    if user.is_superuser:
        return 'admin'
    for role_key, group_name in ROLE_GROUP_MAP.items():
        if user.groups.filter(name=group_name).exists():
            return role_key
    return 'none'


# ─── کلاس استایل ───
class StyledMixin:
    input_class = 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'


# ═══════════════════════════════════════════════════════════
# UserCreateForm
# ═══════════════════════════════════════════════════════════
class UserCreateForm(DuplicateCheckMixin, forms.ModelForm):
    duplicate_model = 'user'
    duplicate_fields = {
        'username': 'نام کاربری',
        'email': 'ایمیل',
    }

    password1 = forms.CharField(
        label='رمز عبور',
        widget=forms.PasswordInput(attrs={'class': StyledMixin.input_class, 'dir': 'ltr'}),
    )
    password2 = forms.CharField(
        label='تکرار رمز عبور',
        widget=forms.PasswordInput(attrs={'class': StyledMixin.input_class, 'dir': 'ltr'}),
    )
    role = forms.ChoiceField(
        label='نقش', choices=ROLE_CHOICES, initial='sales',
        widget=forms.Select(attrs={'class': StyledMixin.input_class}),
    )
    is_active = forms.BooleanField(
        label='فعال', required=False, initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'}),
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': StyledMixin.input_class, 'placeholder': 'نام کاربری', 'dir': 'ltr'}),
            'first_name': forms.TextInput(attrs={'class': StyledMixin.input_class, 'placeholder': 'نام'}),
            'last_name': forms.TextInput(attrs={'class': StyledMixin.input_class, 'placeholder': 'نام خانوادگی'}),
            'email': forms.EmailInput(attrs={'class': StyledMixin.input_class, 'placeholder': 'email@example.com', 'dir': 'ltr'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.duplicate_warnings = []
        self.permission_groups = OrderedDict()

    def clean_username(self):
        from crm.duplicate_check import find_exact_match, normalize_code
        username = (self.cleaned_data.get('username') or '').strip()
        if not username:
            raise forms.ValidationError('نام کاربری الزامی است.')
        existing = find_exact_match(User, 'username', username, normalize_code)
        if existing:
            raise forms.ValidationError(f'⛔ نام کاربری «{username}» قبلاً استفاده شده است.')
        return username

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if email:
            from crm.duplicate_check import find_exact_match, normalize_email
            existing = find_exact_match(User, 'email', email, normalize_email)
            if existing:
                self.add_error('email', f'⛔ ایمیل «{email}» قبلاً برای کاربر «{existing.username}» ثبت شده است.')
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('رمزها با هم مطابقت ندارند')
        if p1 and len(p1) < 6:
            raise forms.ValidationError('رمز عبور باید حداقل ۶ کاراکتر باشد')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.is_active = self.cleaned_data.get('is_active', True)
        role = self.cleaned_data.get('role')
        if role == 'admin':
            user.is_superuser = True
            user.is_staff = True
        else:
            user.is_superuser = False
            user.is_staff = True
        if commit:
            user.save()
            if role in ROLE_GROUP_MAP:
                group, _ = Group.objects.get_or_create(name=ROLE_GROUP_MAP[role])
                user.groups.add(group)
        return user


# ═══════════════════════════════════════════════════════════
# UserEditForm
# ═══════════════════════════════════════════════════════════
class UserEditForm(DuplicateCheckMixin, forms.ModelForm):
    duplicate_model = 'user'
    duplicate_fields = {
        'username': 'نام کاربری',
        'email': 'ایمیل',
    }

    role = forms.ChoiceField(
        label='نقش', choices=ROLE_CHOICES,
        widget=forms.Select(attrs={'class': StyledMixin.input_class}),
    )
    is_active = forms.BooleanField(
        label='فعال', required=False,
        widget=forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'}),
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': StyledMixin.input_class, 'dir': 'ltr'}),
            'first_name': forms.TextInput(attrs={'class': StyledMixin.input_class}),
            'last_name': forms.TextInput(attrs={'class': StyledMixin.input_class}),
            'email': forms.EmailInput(attrs={'class': StyledMixin.input_class, 'dir': 'ltr'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.duplicate_warnings = []
        self.permission_groups = OrderedDict()

        if self.instance and self.instance.pk:
            self.fields['role'].initial = get_user_role(self.instance)
            self._build_permission_fields()

    def _build_permission_fields(self):
        from accounts.permissions import PERMISSIONS, PERMISSION_META

        existing = {
            o.permission_key: o.granted
            for o in self.instance.permission_overrides.all()
        }

        user_role = get_user_role(self.instance)
        role_effective = {
            pk: (user_role in roles) for pk, roles in PERMISSIONS.items()
        }

        for perm_key, meta in PERMISSION_META.items():
            cat, label = meta[0], meta[1]
            description = meta[2] if len(meta) > 2 else ''
            field_name = 'perm__' + perm_key.replace('.', '_')

            if perm_key in existing:
                initial = 'allow' if existing[perm_key] else 'deny'
            else:
                initial = 'inherit'

            self.fields[field_name] = forms.ChoiceField(
                choices=[
                    ('inherit', 'خودکار (از نقش)'),
                    ('allow', '✓ دسترسی'),
                    ('deny', '✗ بدون دسترسی'),
                ],
                initial=initial,
                required=False,
                widget=forms.Select(attrs={
                    'class': 'w-full px-2 py-1.5 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-1 focus:ring-blue-500'
                }),
            )

            self.permission_groups.setdefault(cat, []).append({
                'key': perm_key,
                'field': self[field_name],
                'label': label,
                'description': description,
                'role_status': role_effective.get(perm_key, False),
            })

    def clean_username(self):
        from crm.duplicate_check import find_exact_match, normalize_code
        username = (self.cleaned_data.get('username') or '').strip()
        existing = find_exact_match(User, 'username', username, normalize_code,
                                    exclude_pk=self.instance.pk)
        if existing:
            raise forms.ValidationError(f'⛔ نام کاربری «{username}» قبلاً استفاده شده است.')
        return username

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if email:
            from crm.duplicate_check import find_exact_match, normalize_email
            existing = find_exact_match(User, 'email', email, normalize_email,
                                        exclude_pk=self.instance.pk)
            if existing:
                self.add_error('email', f'⛔ ایمیل «{email}» قبلاً برای کاربر «{existing.username}» ثبت شده است.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_active = self.cleaned_data.get('is_active', True)
        role = self.cleaned_data.get('role')
        if role == 'admin':
            user.is_superuser = True
            user.is_staff = True
        else:
            user.is_superuser = False
            user.is_staff = True
        if commit:
            user.save()
            user.groups.clear()
            if role in ROLE_GROUP_MAP:
                group, _ = Group.objects.get_or_create(name=ROLE_GROUP_MAP[role])
                user.groups.add(group)

            # ذخیره overrideها (فقط برای غیر سوپریوزر)
            from accounts.permissions import PERMISSION_META
            from accounts.models import UserPermissionOverride

            if not user.is_superuser:
                user.permission_overrides.all().delete()
                for perm_key in PERMISSION_META.keys():
                    field_name = 'perm__' + perm_key.replace('.', '_')
                    val = self.cleaned_data.get(field_name, 'inherit')
                    if val == 'allow':
                        UserPermissionOverride.objects.create(
                            user=user, permission_key=perm_key, granted=True,
                        )
                    elif val == 'deny':
                        UserPermissionOverride.objects.create(
                            user=user, permission_key=perm_key, granted=False,
                        )
        return user


# ═══════════════════════════════════════════════════════════
# UserPasswordForm
# ═══════════════════════════════════════════════════════════
class UserPasswordForm(forms.Form):
    password1 = forms.CharField(
        label='رمز جدید',
        widget=forms.PasswordInput(attrs={'class': StyledMixin.input_class, 'dir': 'ltr'}),
    )
    password2 = forms.CharField(
        label='تکرار رمز جدید',
        widget=forms.PasswordInput(attrs={'class': StyledMixin.input_class, 'dir': 'ltr'}),
    )

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('رمزها با هم مطابقت ندارند')
        if p1 and len(p1) < 6:
            raise forms.ValidationError('رمز عبور باید حداقل ۶ کاراکتر باشد')
        return cleaned