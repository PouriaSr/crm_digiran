import jdatetime
from django import forms

from crm.duplicate_check import (
    find_exact_match, find_similar_matches,
    normalize_digits, normalize_email, normalize_phone, normalize_text,
)
from crm.form_mixins import DuplicateCheckMixin
from .models import Customer, CustomerCase, CustomerNote
from products.models import Product
from calls.models import Call, DECLARED_CUSTOMER_STATUS_CHOICES


class CustomerForm(DuplicateCheckMixin, forms.ModelForm):
    """فرم مشتری — با سیستم جامع تشخیص تکراری"""
    duplicate_model = 'customer'
    duplicate_fields = {
        'mobile': 'شماره تماس',
        'national_id': 'کد ملی',
    }

    birth_date = forms.CharField(
        required=False, label='تاریخ تولد',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm',
            'data-jdp': '', 'placeholder': '۱۴۰۵/۰۱/۱۵', 'autocomplete': 'off',
        })
    )

    class Meta:
        model = Customer
        fields = [
            'name', 'mobile', 'email', 'national_id', 'birth_date',
            'stage', 'source', 'ad_source', 'assigned_to', 'address', 'notes',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': 'نام و نام خانوادگی یا نام شرکت'}),
            'mobile': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': '۰۹۱۲۱۲۳۴۵۶۷', 'dir': 'ltr'}),
            'email': forms.EmailInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': 'email@example.com', 'dir': 'ltr'}),
            'national_id': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'placeholder': '۱۲۳۴۵۶۷۸۹۰', 'dir': 'ltr'}),
            'stage': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'ad_source': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'source': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'assigned_to': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'}),
            'address': forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'rows': 3, 'placeholder': 'آدرس کامل'}),
            'notes': forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'rows': 3, 'placeholder': 'یادداشت‌ها'}),
        }

    BASIC_FIELDS = ('name', 'mobile', 'source', 'ad_source', 'notes')

    def __init__(self, *args, for_create=False, limited=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.for_create = for_create
        self.limited = limited
        self.duplicate_warnings = []
        # «وضعیت» فقط دو حالت دارد
        if 'stage' in self.fields:
            self.fields['stage'].label = 'وضعیت'
            self.fields['stage'].choices = [
                ('potential', 'بالقوه'),
                ('lead', 'فاقد شرایط'),
            ]
            self.fields['stage'].required = False
        from ads.models import AdSource
        self.fields['ad_source'].queryset = AdSource.objects.filter(is_active=True)
        self.fields['ad_source'].required = False
        if limited:
            for fname in list(self.fields):
                if fname not in self.BASIC_FIELDS:
                    self.fields.pop(fname, None)

        if for_create:
            for fname in ('email', 'stage'):
                self.fields.pop(fname, None)
            # همه‌ی منبع‌های معتبر مدل (وگرنه «تماس مستقیم» رد می‌شد)
            self.fields['source'].choices = self._meta.model.SOURCE_CHOICES
            attrs = self.fields['source'].widget.attrs
            attrs['x-model'] = 'sourceVal'
        self.fields['notes'].required = True
        if self.instance and self.instance.pk and self.instance.birth_date:
            g = self.instance.birth_date
            j = jdatetime.date.fromgregorian(date=g)
            self.initial['birth_date'] = j.strftime('%Y/%m/%d')

    # ═══════════════════════════════════════════════════════════
    # نرمال‌سازی ورودی‌ها
    # ═══════════════════════════════════════════════════════════
    def save(self, commit=True):
        customer = super().save(commit=False)

        # «وضعیت» تعیین‌کننده‌ی برچسب، تیک پیگیری و دسترسی‌هاست
        new_stage = self.cleaned_data.get('stage')
        if new_stage in ('potential', 'lead'):
            customer.stage = new_stage
            customer.needs_followup = (new_stage == 'potential')

        if commit:
            customer.save()
        return customer

    def clean_mobile(self):
        mobile = normalize_phone(self.cleaned_data.get('mobile'))
        if mobile:
            if not (mobile.isdigit() and len(mobile) == 11 and mobile.startswith('09')):
                raise forms.ValidationError(
                    'شماره تماس باید ۱۱ رقم و با ۰۹ شروع شود (مثال: ۰۹۱۲۱۲۳۴۵۶۷).'
                )
        if mobile:
            qs = Customer.objects.filter(mobile=mobile)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            other = qs.first()
            if other:
                raise forms.ValidationError(
                    f'مشتری فعال «{other.name}» با این شماره از قبل ثبت شده است.'
                )
        return mobile

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if name:
            qs = Customer.objects.filter(name__iexact=name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            other = qs.first()
            if other:
                raise forms.ValidationError(
                    f'مشتری فعال «{other.name}» با این نام از قبل ثبت شده است.'
                )
        return name

    def clean_national_id(self):
        value = normalize_digits(self.cleaned_data.get('national_id', '') or '')
        value = value.replace(' ', '').replace('-', '').strip()
        if not value:
            return ''

        if not value.isdigit() or len(value) != 10:
            raise forms.ValidationError('کد ملی باید دقیقاً ۱۰ رقم باشد.')

        # ارقام تکراری (مثل ۱۱۱۱۱۱۱۱۱۱) معتبر نیست
        if len(set(value)) == 1:
            raise forms.ValidationError('کد ملی وارد شده معتبر نیست.')

        # الگوریتم رسمی کد ملی ایران
        check = int(value[9])
        total = sum(int(value[i]) * (10 - i) for i in range(9))
        remainder = total % 11
        if not ((remainder < 2 and check == remainder)
                or (remainder >= 2 and check == 11 - remainder)):
            raise forms.ValidationError('کد ملی وارد شده معتبر نیست.')

        return value

    def clean_email(self):
        email = self.cleaned_data.get('email', '')
        return str(email).strip().lower() if email else ''

    def clean_birth_date(self):
        value = self.cleaned_data.get('birth_date')
        if not value:
            return None
        if hasattr(value, 'year'):
            return value
        value = normalize_digits(str(value).strip()).replace('-', '/').replace('.', '/')
        if ' ' in value:
            value = value.split(' ', 1)[0]
        parts = value.split('/')
        if len(parts) != 3:
            raise forms.ValidationError('فرمت تاریخ باید به‌صورت ۱۳۷۸/۱۲/۱۶ باشد')
        try:
            y, m, d = map(int, parts)
            return jdatetime.date(y, m, d).togregorian()
        except (ValueError, TypeError):
            raise forms.ValidationError('تاریخ وارد شده معتبر نیست')

    # ═══════════════════════════════════════════════════════════
    # چک تکراری
    # ═══════════════════════════════════════════════════════════
    def clean(self):
        cleaned = super().clean()
        self.duplicate_warnings = []

        exclude_pk = self.instance.pk if self.instance and self.instance.pk else None

        # ─── Exact blocks (چک روی فعال + غیرفعال) ───
        mobile = cleaned.get('mobile')
        if mobile:
            existing = find_exact_match(
                Customer, 'mobile', mobile, normalize_phone, exclude_pk,
                manager=Customer.all_objects,
            )
            if existing:
                if existing.is_deleted:
                    self.add_error(
                        'mobile',
                        f'⛔ شماره تماس «{mobile}» قبلاً برای «{existing.name}» ثبت شده '
                        f'ولی آن مشتری غیرفعال شده — ابتدا از صفحه‌ی «مشتریان غیرفعال» بازگردانی کنید.'
                    )
                else:
                    self.add_error(
                        'mobile',
                        f'⛔ شماره تماس «{mobile}» قبلاً برای «{existing.name}» ثبت شده است.'
                    )

        nid = cleaned.get('national_id')
        if nid:
            existing = find_exact_match(
                Customer, 'national_id', nid, normalize_digits, exclude_pk,
                manager=Customer.all_objects,
            )
            if existing:
                tag = ' (غیرفعال)' if existing.is_deleted else ''
                self.add_error(
                    'national_id',
                    f'⛔ کد ملی «{nid}» قبلاً برای «{existing.name}»{tag} ثبت شده است.'
                )

        # ─── Similar warnings ───
        name = cleaned.get('name')
        if name:
            for obj, ratio in find_similar_matches(Customer, 'name', name, normalize_text, exclude_pk=exclude_pk):
                self.duplicate_warnings.append({
                    'field': 'name', 'label': 'نام مشتری',
                    'value': name, 'match': obj, 'ratio': round(ratio * 100, 1),
                })

        email = cleaned.get('email')
        if email:
            for obj, ratio in find_similar_matches(Customer, 'email', email, normalize_email, exclude_pk=exclude_pk):
                self.duplicate_warnings.append({
                    'field': 'email', 'label': 'ایمیل',
                    'value': email, 'match': obj, 'ratio': round(ratio * 100, 1),
                })

        return cleaned


class CustomerNoteForm(forms.ModelForm):
    """فرم ثبت/ویرایش یادداشت مشتری"""

    class Meta:
        model = CustomerNote
        fields = ['text', 'is_pinned']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm', 'rows': 3, 'placeholder': 'متن یادداشت...'}),
            'is_pinned': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'}),
        }

    def clean_text(self):
        text = self.cleaned_data.get('text', '').strip()
        if not text:
            raise forms.ValidationError('متن یادداشت نمی‌تواند خالی باشد.')
        return text

# وضعیت مشتری در فرم ثبت تماس — از مدل Call می‌آید (تک‌منبع حقیقت)
CUSTOMER_STATUS_CHOICES = DECLARED_CUSTOMER_STATUS_CHOICES


class HubCallForm(forms.Form):
    mobile = forms.CharField(label='شماره تماس', max_length=15, required=True,
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 text-lg font-mono tracking-widest bg-white', 'dir': 'ltr', 'placeholder': '09123456789', 'id': 'hub_call_mobile', 'inputmode': 'numeric', 'minlength': 11, 'maxlength': 11, 'pattern': '[0-9۰-۹٠-٩]{11}', '@input.debounce.500ms': 'checkMobile()'}))
    name = forms.CharField(label='نام و نام خانوادگی', max_length=200, required=True,
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all', 'id': 'hub_call_name', 'autocomplete': 'name', 'placeholder': 'مثلاً: مریم احمدی', 'pattern': r'[^\p{N}]+', 'title': 'نام و نام خانوادگی نباید شامل عدد باشد.', '@input': 'validateName($el)', ':aria-invalid': "nameInvalid ? 'true' : 'false'", 'aria-describedby': 'hub_call_name_error'}))
    
    call_type = forms.ChoiceField(label='نوع تماس', choices=[
        ('incoming', 'تماس مشتری'),
        ('missed', 'از دست رفته'),
        ('divar', 'چت دیوار'),
        ('ads', 'تبلیغات'),
        ('followup', 'پیگیری'),
        ('busy', 'مشغول'),
    ], widget=forms.Select(attrs={'class': 'w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all', 'x-model': 'callType', '@change': "callStatus = ({missed: 'missed', busy: 'busy'})[callType] || 'answered'; purpose = callType === 'followup' ? 'followup' : 'sale'"}))
    
    purpose = forms.ChoiceField(
        label='هدف تماس', choices=Call.CALL_PURPOSE_CHOICES, required=False,
        widget=forms.Select(attrs={'x-model': 'purpose'}))
    call_status = forms.ChoiceField(
        label='وضعیت تماس', required=False,
        choices=[choice for choice in Call.CALL_STATUS_CHOICES if choice[0] != 'followup'],
        widget=forms.Select(attrs={'x-model': 'callStatus'}))
    customer_analysis = forms.ChoiceField(
        label='تحلیل مشتری', required=False,
        choices=[('lead', 'فاقد شرایط'), ('potential', 'قصد خرید دارد')],
        widget=forms.Select(attrs={'x-model': 'customerAnalysis', '@change': 'applyCustomerAnalysis($el.value)'}))
    requested_condition = forms.ChoiceField(
        label='شرایط درخواستی', required=False,
        choices=[('', 'انتخاب شرایط…')] + CustomerCase.CONDITION_CHOICES)
    send_address = forms.BooleanField(
        label='ارسال آدرس', required=False,
        widget=forms.CheckboxInput(attrs={
            'x-model': 'sendAddress', 'id': 'hub_send_address',
            'class': 'sr-only peer',
        }))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            from accounts.permissions import has_permission
            if not has_permission(user, 'customers.case'):
                self.fields['purpose'].choices = [
                    choice for choice in self.fields['purpose'].choices if choice[0] != 'info'
                ]
        for field in ('purpose', 'call_status', 'customer_analysis', 'requested_condition'):
            self.fields[field].widget.attrs['class'] = (
                'w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl '
                'focus:bg-white focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500'
            )

    source = forms.ModelChoiceField(label='منبع تماس', queryset=__import__('ads.models', fromlist=['AdSource']).AdSource.objects.filter(is_active=True), required=False,
        widget=forms.Select(attrs={'class': 'w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all'}))
    
    needs_followup = forms.BooleanField(label='نیاز به پیگیری', required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-5 h-5 rounded text-orange-600 border-gray-300 focus:ring-orange-500',
            'x-model': 'needsFollowup',
            ':disabled': "customerAnalysis === 'potential'",
            '@change': 'sendAddress = $el.checked',
            'id': 'hub_needs_followup',
        }))
    
    follow_up_date = forms.CharField(label='تاریخ پیگیری', required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-4 focus:ring-orange-500/10 focus:border-orange-500 transition-all',
            'placeholder': '۱۴۰۵/۰۸/۱۵', 'autocomplete': 'off', 'id': 'hub_followup_date',
            'data-jdp': '', 'data-jdp-time': 'false', ':required': 'needsFollowup',
        }))

    follow_up_time = forms.CharField(label='ساعت پیگیری', required=False,
        widget=forms.TimeInput(attrs={
            'type': 'time', 'id': 'hub_followup_time', ':required': 'needsFollowup',
            'class': 'w-full px-4 py-3 bg-white border border-orange-200 rounded-xl',
        }))

    notes = forms.CharField(label='شرح مکالمه', required=True,
        widget=forms.Textarea(attrs={'class': 'w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all resize-none', 'rows': 3, 'placeholder': 'شرح مکالمه...'}))

    def clean_name(self):
        name = self.cleaned_data['name']
        if any(character.isnumeric() for character in name):
            raise forms.ValidationError('نام و نام خانوادگی نباید شامل عدد باشد.')
        return name

    def clean_mobile(self):
        mobile = normalize_digits(self.cleaned_data['mobile'])
        if len(mobile) != 11 or not mobile.isascii() or not mobile.isdigit():
            raise forms.ValidationError('شماره تماس باید دقیقاً ۱۱ رقم باشد.')
        return mobile

    def clean(self):
        data = super().clean()
        if data.get('customer_analysis') == 'potential':
            data['needs_followup'] = True
        if data.get('needs_followup'):
            from .scheduling import parse_followup_time
            due_time = parse_followup_time(data.get('follow_up_time'))
            if due_time is None:
                self.add_error('follow_up_time', 'ساعت پیگیری را به شکل ۱۴:۳۰ وارد کنید.')
            else:
                data['follow_up_time'] = due_time
            value = normalize_digits(data.get('follow_up_date') or '').replace('-', '/')
            try:
                year, month, day = map(int, value.split('/'))
                data['follow_up_due'] = jdatetime.date(year, month, day).togregorian()
            except (ValueError, TypeError):
                self.add_error('follow_up_date', 'برای پیگیری، یک تاریخ شمسی معتبر وارد کنید.')
        return data



class CustomerCaseForm(forms.ModelForm):
    """فرم پرونده‌ی مشتری — تب سوم مرکز مشتریان"""

    active_loans = forms.MultipleChoiceField(
        label='وام‌های فعال',
        choices=CustomerCase.LOAN_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'w-4 h-4 rounded text-blue-600 border-gray-300 focus:ring-blue-500',
        }),
    )

    class Meta:
        model = CustomerCase
        fields = [
            'condition', 'cheque_owner', 'cheque_other_name', 'cheque_other_phone',
            'job', 'credit_rank', 'active_loans', 'product', 'quantity', 'visit_result',
        ]
        widgets = {
            'condition': forms.Select(attrs={
                'class': 'w-full px-3 py-2 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:border-blue-500 focus:outline-none',
                'x-model': 'cond',
            }),
            'cheque_owner': forms.Select(attrs={
                'class': 'w-full px-3 py-2 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:border-blue-500 focus:outline-none',
                'x-model': 'owner',
            }),
            'cheque_other_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:border-blue-500 focus:outline-none',
                'placeholder': 'نام صاحب چک',
            }),
            'cheque_other_phone': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:border-blue-500 focus:outline-none',
                'placeholder': '۰۹۱۲...', 'dir': 'ltr',
            }),
            'job': forms.Select(attrs={
                'class': 'w-full px-3 py-2 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:border-blue-500 focus:outline-none',
            }),
            'credit_rank': forms.Select(attrs={
                'class': 'w-full px-3 py-2 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:border-blue-500 focus:outline-none',
            }),
            'product': forms.Select(attrs={
                'class': 'w-full px-3 py-2 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:border-blue-500 focus:outline-none',
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:border-blue-500 focus:outline-none',
                'min': 1,
            }),
            'visit_result': forms.Select(attrs={
                'class': 'w-full px-3 py-2 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:border-blue-500 focus:outline-none',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True).order_by('name')
        self.fields['product'].empty_label = 'انتخاب کالا...'
        self.fields['condition'].required = True
        self.fields['job'].required = True
        self.fields['credit_rank'].required = True
        self.fields['visit_result'].required = True

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('condition') == 'cheque':
            if not cleaned.get('cheque_owner'):
                self.add_error('cheque_owner', 'برای چک، «برای خودش / برای دیگری» را انتخاب کنید.')
            elif cleaned.get('cheque_owner') == 'other':
                if not cleaned.get('cheque_other_name'):
                    self.add_error('cheque_other_name', 'نام صاحب چک الزامی است.')
                if not cleaned.get('cheque_other_phone'):
                    self.add_error('cheque_other_phone', 'شماره تماس صاحب چک الزامی است.')
        return cleaned
