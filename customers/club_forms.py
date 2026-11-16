import jdatetime
from django import forms

from crm.numerals import ascii_digits

from .club_models import ClubAccount, ClubPayment, LoanProgram
from .models import CustomerCase


FIELD_CLASS = 'w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm'


class LoanEvaluationForm(forms.Form):
    requested_credit = forms.TypedChoiceField(label='رقم پیشنهادی وام', coerce=int, choices=())
    proposed_down_payment = forms.IntegerField(
        label='مقدار پیش‌پرداخت', min_value=0,
        widget=forms.NumberInput(attrs={
            'min': 0, 'step': 100000, 'inputmode': 'numeric',
            'placeholder': 'مثلاً ۱۴٬۳۰۰٬۰۰۰ تومان',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        credits = LoanProgram.objects.filter(is_active=True).values_list('credit_limit', flat=True).distinct().order_by('credit_limit')
        self.fields['requested_credit'].choices = [(x, f'{x:,} تومان') for x in credits]
        self.fields['proposed_down_payment'].initial = 0
        for field in self.fields.values():
            field.widget.attrs['class'] = FIELD_CLASS


class ClubSelectionForm(forms.Form):
    evaluation = forms.IntegerField(widget=forms.HiddenInput)
    program = forms.IntegerField(widget=forms.HiddenInput)
    product = forms.IntegerField(widget=forms.HiddenInput)
    delivery_type = forms.ChoiceField(label='نوع تحویل', choices=ClubAccount.DELIVERY_TYPES)
    club_fee = forms.IntegerField(label='هزینه باشگاه مشتریان', min_value=0, initial=1_000_000, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('delivery_type', 'club_fee'):
            self.fields[name].widget.attrs['class'] = FIELD_CLASS


class ClubPaymentForm(forms.ModelForm):
    due_date = forms.CharField(
        label='سررسید', required=False,
        widget=forms.TextInput(attrs={
            'data-jdp': '', 'data-jdp-time': 'false',
            'placeholder': 'انتخاب تاریخ شمسی…', 'autocomplete': 'off',
        }),
    )

    class Meta:
        model = ClubPayment
        fields = ['payment_type', 'amount', 'due_date', 'status', 'receipt', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
            'receipt': forms.FileInput(attrs={'accept': '.jpg,.jpeg,.png,.pdf'}),
        }

    def __init__(self, *args, account=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.account = account
        next_installment = None
        if account:
            next_installment = account.payments.filter(
                payment_type='installment', status__in=('scheduled', 'overdue'), receipt='',
            ).order_by('due_date', 'pk').first()
        if next_installment:
            jalali_due = jdatetime.date.fromgregorian(date=next_installment.due_date).strftime('%Y/%m/%d')
            self.fields['due_date'].widget.attrs.update({
                'data-next-installment-date': jalali_due,
                'data-next-installment-amount': next_installment.amount,
            })
            if not self.is_bound and not self.instance.pk:
                self.initial.update(
                    payment_type='installment', amount=next_installment.amount,
                    due_date=jalali_due, status=next_installment.status,
                )
        elif self.instance.pk and self.instance.due_date:
            self.initial['due_date'] = jdatetime.date.fromgregorian(date=self.instance.due_date).strftime('%Y/%m/%d')
        for field in self.fields.values():
            field.widget.attrs['class'] = FIELD_CLASS

    def clean_due_date(self):
        value = ascii_digits(self.cleaned_data.get('due_date', '')).strip()
        if not value:
            return None
        try:
            year, month, day = map(int, value.replace('-', '/').split('/'))
            return jdatetime.date(year, month, day).togregorian()
        except (TypeError, ValueError, OverflowError):
            raise forms.ValidationError('سررسید را از تقویم شمسی انتخاب کنید.')

    def clean_receipt(self):
        receipt = self.cleaned_data.get('receipt')
        if not receipt:
            return receipt
        if receipt.size > 5 * 1024 * 1024:
            raise forms.ValidationError('حجم فاکتور یا رسید نباید بیشتر از ۵ مگابایت باشد.')
        allowed = {'image/jpeg', 'image/png', 'application/pdf'}
        content_type = getattr(receipt, 'content_type', '')
        if content_type and content_type not in allowed:
            raise forms.ValidationError('فاکتور یا رسید باید تصویر JPG/PNG یا فایل PDF باشد.')
        return receipt


class ClubPaymentReceiptForm(forms.ModelForm):
    class Meta:
        model = ClubPayment
        fields = ['receipt', 'notes']
        widgets = {
            'receipt': forms.FileInput(attrs={'accept': '.jpg,.jpeg,.png,.pdf', 'required': True}),
            'notes': forms.TextInput(attrs={'placeholder': 'شماره پیگیری یا توضیح پرداخت'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['receipt'].required = True
        for field in self.fields.values():
            field.widget.attrs['class'] = FIELD_CLASS

    def clean_receipt(self):
        receipt = self.cleaned_data['receipt']
        if receipt.size > 5 * 1024 * 1024:
            raise forms.ValidationError('حجم فاکتور یا رسید نباید بیشتر از ۵ مگابایت باشد.')
        content_type = getattr(receipt, 'content_type', '')
        if content_type and content_type not in {'image/jpeg', 'image/png', 'application/pdf'}:
            raise forms.ValidationError('فاکتور یا رسید باید تصویر JPG/PNG یا فایل PDF باشد.')
        return receipt


class LoanProgramSettingsForm(forms.ModelForm):
    allowed_customer_ranks = forms.MultipleChoiceField(
        label='رتبه‌های مجاز متقاضی', choices=CustomerCase.CREDIT_RANK_CHOICES,
        widget=forms.CheckboxSelectMultiple,
    )
    allowed_guarantor_ranks = forms.MultipleChoiceField(
        label='رتبه‌های مجاز ضامن', choices=CustomerCase.CREDIT_RANK_CHOICES,
        required=False, widget=forms.CheckboxSelectMultiple,
    )
    allowed_guarantor_ranks_for_b = forms.MultipleChoiceField(
        label='رتبه‌های ضامن وقتی متقاضی B است', choices=CustomerCase.CREDIT_RANK_CHOICES,
        required=False, widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = LoanProgram
        fields = ['provider', 'term_months', 'credit_limit', 'monthly_installment', 'purchase_limit',
                  'no_down_purchase_limit', 'down_payment', 'allowed_customer_ranks',
                  'allowed_guarantor_ranks', 'allowed_guarantor_ranks_for_b',
                  'guarantee', 'employment_note', 'is_active', 'order']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial['allowed_customer_ranks'] = self.instance.allowed_customer_ranks
            self.initial['allowed_guarantor_ranks'] = self.instance.allowed_guarantor_ranks
            self.initial['allowed_guarantor_ranks_for_b'] = self.instance.allowed_guarantor_ranks_for_b
        for name, field in self.fields.items():
            if name not in ('allowed_customer_ranks', 'allowed_guarantor_ranks',
                            'allowed_guarantor_ranks_for_b', 'is_active'):
                field.widget.attrs['class'] = FIELD_CLASS
