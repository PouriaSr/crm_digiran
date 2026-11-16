from django import forms

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
    club_fee = forms.IntegerField(label='هزینه باشگاه مشتریان', min_value=0, initial=0, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('delivery_type', 'club_fee'):
            self.fields[name].widget.attrs['class'] = FIELD_CLASS


class ClubPaymentForm(forms.ModelForm):
    class Meta:
        model = ClubPayment
        fields = ['payment_type', 'amount', 'due_date', 'status', 'receipt', 'notes']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
            'receipt': forms.FileInput(attrs={'accept': '.jpg,.jpeg,.png,.pdf'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = FIELD_CLASS

    def clean_receipt(self):
        receipt = self.cleaned_data.get('receipt')
        if not receipt:
            return receipt
        if receipt.size > 5 * 1024 * 1024:
            raise forms.ValidationError('حجم رسید نباید بیشتر از ۵ مگابایت باشد.')
        allowed = {'image/jpeg', 'image/png', 'application/pdf'}
        content_type = getattr(receipt, 'content_type', '')
        if content_type and content_type not in allowed:
            raise forms.ValidationError('رسید باید تصویر JPG/PNG یا فایل PDF باشد.')
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
