from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from accounts.permissions import has_permission, require_permission
from products.models import Product

from .access import can_edit_card
from .club_forms import (
    ClubAccountEditForm, ClubPaymentForm, ClubPaymentReceiptForm, ClubSelectionForm,
    LoanEvaluationForm, LoanProgramSettingsForm,
)
from .club_models import ClubAccount, ClubPayment, LoanEvaluation, LoanProgram
from .club_service import (
    covered_purchase_amount, create_payment_schedule, evaluate_case, loan_purchase_amount,
    maximum_purchase_price, program_eligibility, purchase_budget, purchase_difference,
    reconcile_payment_schedule,
)
from .models import Reception


def _reception(request, pk, operation):
    rec = get_object_or_404(Reception.objects.select_related('customer', 'customer__case'), pk=pk,
                            workflow_version=2, person_type='customer', case_result='bought')
    if not can_edit_card(request.user, rec.customer):
        raise PermissionDenied('این پرونده در محدوده مسئولیت شما نیست.')
    if not has_permission(request.user, operation):
        raise PermissionDenied('مجوز این عملیات باشگاه مشتریان را ندارید.')
    return rec


@login_required
@require_permission('customers.club')
@require_POST
@transaction.atomic
def evaluate(request, pk):
    rec = _reception(request, pk, 'customers.club_evaluate')
    form = LoanEvaluationForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'errors': form.errors.get_json_data()}, status=400)
    case = rec.customer.case
    if not case.contract_number:
        return JsonResponse({'ok': False, 'message': 'شماره قرارداد پرونده ثبت نشده است؛ پرونده را دوباره ذخیره کنید.'}, status=409)
    programs, products, rejected = evaluate_case(case, **form.cleaned_data)
    if not programs:
        if rejected:
            details = '؛ '.join(dict.fromkeys(
                f"{item['program']}: {item['reason']}" for item in rejected
            ))
            message = 'هیچ وامی شرایط این پرونده را ندارد. ' + details
        else:
            message = (
                'برای ترکیب مبلغ وام و پیش‌پرداخت انتخاب‌شده، طرح فعالی تعریف نشده است. '
                'مقادیر دیگری انتخاب کنید یا تنظیمات طرح‌های وام را بررسی کنید.'
            )
        return JsonResponse({'ok': False, 'message': message, 'rejected': rejected}, status=422)
    if not products:
        max_budget = max(maximum_purchase_price(item, form.cleaned_data['proposed_down_payment']) for item in programs)
        return JsonResponse({
            'ok': False,
            'message': (
                f'وام واجد شرایط پیدا شد، اما گوشی فعال و موجود تا سقف {max_budget:,} تومان ثبت نشده است. '
                'موجودی، قیمت و دسته‌بندی «گوشی/موبایل» کالاها را بررسی کنید.'
            ),
            'rejected': rejected,
        }, status=422)
    evaluation = LoanEvaluation.objects.create(
        reception=rec, case=case, contract_number=case.contract_number,
        result_program_ids=[x.pk for x in programs], result_product_ids=[x.pk for x in products],
        snapshot={
            'credit_rank': case.credit_rank, 'guarantor_name': case.guarantor_name,
            'guarantor_credit_rank': case.guarantor_credit_rank, 'job': case.job,
            'active_loans': case.active_loans or [], 'rejected': rejected,
        }, created_by=request.user, **form.cleaned_data,
    )
    return JsonResponse({
        'ok': True, 'evaluation': evaluation.pk, 'contract': evaluation.contract_number,
        'programs': [{
            'id': item.pk, 'title': str(item), 'provider': item.get_provider_display(),
            'months': item.term_months, 'credit': item.credit_limit,
            'monthly': item.monthly_installment,
            'budget': maximum_purchase_price(item, evaluation.proposed_down_payment),
            'contribution': covered_purchase_amount(item, evaluation.proposed_down_payment),
            'loan_purchase': loan_purchase_amount(item, evaluation.proposed_down_payment),
            'down': item.down_payment, 'entered_down': evaluation.proposed_down_payment,
            'guarantee': item.guarantee,
            'employment': item.employment_note,
        } for item in programs],
        'products': [{'id': item.pk, 'name': item.name, 'code': item.code, 'price': int(item.price),
                      'stock': item.stock} for item in products],
        'rejected': rejected,
    })


@login_required
@require_permission('customers.club')
@require_POST
@transaction.atomic
def select_offer(request, pk):
    rec = _reception(request, pk, 'customers.club_select')
    account = ClubAccount.objects.select_for_update().filter(customer=rec.customer).first()
    if account and not has_permission(request.user, 'customers.club_edit'):
        raise PermissionDenied('مجوز اعمال ارزیابی مجدد روی قرارداد باشگاه را ندارید.')
    form = ClubSelectionForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'message': 'طرح، گوشی و نوع تحویل را کامل انتخاب کنید.'}, status=400)
    evaluation = get_object_or_404(LoanEvaluation.objects.select_for_update(), pk=form.cleaned_data['evaluation'],
                                   reception=rec, status='ready')
    program = get_object_or_404(LoanProgram, pk=form.cleaned_data['program'], is_active=True)
    product = get_object_or_404(Product.objects.select_for_update(), pk=form.cleaned_data['product'], is_active=True)
    if program.pk not in evaluation.result_program_ids or product.pk not in evaluation.result_product_ids:
        return JsonResponse({'ok': False, 'message': 'پیشنهاد انتخابی متعلق به این ارزیابی نیست.'}, status=409)
    accepted, reason = program_eligibility(program, rec.customer.case)
    if (not accepted or product.stock < 1 or
            product.price > maximum_purchase_price(program, evaluation.proposed_down_payment)):
        return JsonResponse({'ok': False, 'message': reason or 'قیمت یا موجودی گوشی از زمان ارزیابی تغییر کرده است.'}, status=409)
    delivery = form.cleaned_data['delivery_type']
    panel_url = 'https://example.com/b2b' if delivery == 'instant' else 'https://example.com/b2c'
    guarantee = ' · '.join(x for x in (program.employment_note, program.guarantee) if x)
    down_payment = evaluation.proposed_down_payment
    loan_purchase = loan_purchase_amount(program, down_payment)
    difference = purchase_difference(program, down_payment, product.price)
    club_fee = form.cleaned_data.get('club_fee')
    if club_fee is None:
        club_fee = 1_000_000
    main_purchase = loan_purchase + down_payment
    account_values = {
        'evaluation': evaluation, 'loan_program': program, 'product': product,
        'delivery_type': delivery, 'panel_url': panel_url,
        'customer_credit_rank': rec.customer.case.credit_rank,
        'guarantor_name': rec.customer.case.guarantor_name,
        'guarantor_credit_rank': rec.customer.case.guarantor_credit_rank,
        'guarantee_snapshot': guarantee, 'club_fee': club_fee,
        'loan_purchase_amount': loan_purchase, 'down_payment_amount': down_payment,
        'main_purchase_amount': main_purchase,
        'purchase_difference_amount': difference,
        'total_customer_payable': main_purchase - difference + club_fee,
        'selected_by': request.user,
    }
    is_reevaluation = account is not None
    if is_reevaluation:
        for field, value in account_values.items():
            setattr(account, field, value)
        account.save()
    else:
        account = ClubAccount.objects.create(
            customer=rec.customer, reception=rec, contract_number=evaluation.contract_number,
            **account_values,
        )
    evaluation.status = 'selected'
    evaluation.save(update_fields=['status'])
    LoanEvaluation.objects.filter(reception=rec).exclude(pk=evaluation.pk).filter(
        status__in=('ready', 'selected'),
    ).update(status='expired')
    if is_reevaluation:
        reconcile_payment_schedule(account, request.user)
    else:
        create_payment_schedule(account)
    from hr.task_automation import sync_club_account
    sync_club_account(account)
    difference_text = f' مابه‌التفاوت {difference:,} تومان نیز برای ثبت رسید در برنامه پرداخت ایجاد شد.' if difference else ''
    if is_reevaluation:
        message = f'ارزیابی مجدد روی قرارداد {account.contract_number} اعمال شد؛ پرداخت‌ها و رسیدهای قطعی حفظ شدند.{difference_text}'
    else:
        message = f'قرارداد {account.contract_number} ثبت شد؛ مشتری به باشگاه اضافه شد.{difference_text}'
    return JsonResponse({'ok': True, 'message': message,
                         'redirect': f"{reverse('customers:hub')}?tab=club&r={rec.pk}"})


@login_required
@require_permission('customers.club')
@require_POST
@transaction.atomic
def edit_account(request, pk):
    account = get_object_or_404(
        ClubAccount.objects.select_for_update().select_related(
            'customer', 'customer__case', 'reception', 'loan_program', 'product',
        ), pk=pk,
    )
    if not has_permission(request.user, 'customers.club_edit') or not can_edit_card(request.user, account.customer):
        raise PermissionDenied('مجوز ویرایش قرارداد باشگاه این مشتری را ندارید.')
    old_product_id = account.product_id
    form = ClubAccountEditForm(request.POST, instance=account)
    if not form.is_valid():
        messages.error(request, 'قرارداد ویرایش نشد: ' + '، '.join(e for values in form.errors.values() for e in values))
        return redirect(f"{reverse('customers:hub')}?tab=club&r={account.reception_id}&club_edit=1#club-account-edit")
    updated = form.save(commit=False)
    accepted, reason = program_eligibility(updated.loan_program, account.customer.case)
    if not accepted:
        messages.error(request, 'طرح انتخابی با پرونده سازگار نیست: ' + reason)
        return redirect(f"{reverse('customers:hub')}?tab=club&r={account.reception_id}&club_edit=1#club-account-edit")
    main_purchase = updated.loan_program.purchase_limit + updated.down_payment_amount
    if updated.product.price > main_purchase:
        messages.error(request, 'قیمت گوشی از مجموع سقف خرید و پیش‌پرداخت قرارداد بیشتر است.')
        return redirect(f"{reverse('customers:hub')}?tab=club&r={account.reception_id}&club_edit=1#club-account-edit")
    if updated.product_id != old_product_id and updated.product.stock < 1:
        messages.error(request, 'گوشی انتخابی موجودی قابل فروش ندارد.')
        return redirect(f"{reverse('customers:hub')}?tab=club&r={account.reception_id}&club_edit=1#club-account-edit")
    updated.panel_url = 'https://example.com/b2b' if updated.delivery_type == 'instant' else 'https://example.com/b2c'
    updated.loan_purchase_amount = updated.loan_program.purchase_limit
    updated.main_purchase_amount = main_purchase
    updated.purchase_difference_amount = max(0, main_purchase - int(updated.product.price))
    updated.total_customer_payable = main_purchase - updated.purchase_difference_amount + updated.club_fee
    updated.save()
    reconcile_payment_schedule(updated, request.user)
    from hr.task_automation import sync_club_account
    sync_club_account(updated)
    messages.success(request, 'قرارداد باشگاه و پرداخت‌های آینده با موفقیت به‌روزرسانی شدند؛ سوابق پرداخت‌شده تغییر نکردند.')
    return redirect(f"{reverse('customers:hub')}?tab=club&r={updated.reception_id}")


@login_required
@require_permission('customers.club')
@require_POST
@transaction.atomic
def add_payment(request, pk):
    account = get_object_or_404(ClubAccount.objects.select_related('customer'), pk=pk)
    if not has_permission(request.user, 'customers.club_payment') or not can_edit_card(request.user, account.customer):
        raise PermissionDenied('مجوز ثبت پرداخت این مشتری را ندارید.')
    scheduled_installment = None
    if request.POST.get('payment_type') == 'installment':
        scheduled_installment = account.payments.filter(
            payment_type='installment', status__in=('scheduled', 'overdue'), receipt='',
        ).order_by('due_date', 'pk').first()
    old_receipt = scheduled_installment.receipt.name if scheduled_installment and scheduled_installment.receipt else ''
    form = ClubPaymentForm(
        request.POST, request.FILES, account=account, instance=scheduled_installment,
    )
    if form.is_valid():
        payment = form.save(commit=False)
        payment.account, payment.created_by = account, request.user
        payment.save()
        if old_receipt and request.FILES.get('receipt') and old_receipt != payment.receipt.name:
            payment.receipt.storage.delete(old_receipt)
        from hr.task_automation import sync_club_payment
        sync_club_payment(payment)
        message = 'قسط برنامه‌ریزی‌شده به‌روزرسانی شد.' if scheduled_installment else 'پرداخت و مدرک آن در باشگاه مشتریان ثبت شد.'
        messages.success(request, message)
    else:
        messages.error(request, 'اطلاعات پرداخت کامل نیست: ' + '، '.join(e for values in form.errors.values() for e in values))
    return redirect(f"{reverse('customers:hub')}?tab=club&r={account.reception_id}")


@login_required
@require_permission('customers.club')
@require_GET
def receipt(request, pk):
    payment = get_object_or_404(ClubPayment.objects.select_related('account__customer'), pk=pk)
    if not has_permission(request.user, 'customers.club_payment') or not can_edit_card(request.user, payment.account.customer):
        raise PermissionDenied('مجوز مشاهده این رسید را ندارید.')
    if not payment.receipt:
        return HttpResponse('رسیدی ثبت نشده است.', status=404)
    return FileResponse(payment.receipt.open('rb'), as_attachment=True,
                        filename=Path(payment.receipt_name or payment.receipt.name).name)


@login_required
@require_permission('customers.club')
@require_POST
@transaction.atomic
def update_payment_receipt(request, pk):
    payment = get_object_or_404(
        ClubPayment.objects.select_for_update().select_related('account__customer', 'account__reception'), pk=pk,
    )
    if (payment.payment_type not in {'purchase_difference', 'club_fee', 'installment'} or
            not has_permission(request.user, 'customers.club_payment') or
            not can_edit_card(request.user, payment.account.customer)):
        raise PermissionDenied('مجوز ثبت رسید این پرداخت را ندارید.')
    old_receipt = payment.receipt.name if payment.receipt else ''
    form = ClubPaymentReceiptForm(request.POST, request.FILES, instance=payment)
    if form.is_valid():
        updated = form.save(commit=False)
        updated.status = 'paid'
        updated.created_by = updated.created_by or request.user
        updated.save()
        if old_receipt and old_receipt != updated.receipt.name:
            updated.receipt.storage.delete(old_receipt)
        from hr.task_automation import sync_club_payment
        sync_club_payment(updated)
        messages.success(request, f'رسید {updated.get_payment_type_display()} ثبت شد.')
    else:
        messages.error(request, 'رسید ثبت نشد: ' + '، '.join(e for values in form.errors.values() for e in values))
    return redirect(f"{reverse('customers:hub')}?tab=club&r={payment.account.reception_id}")


@login_required
@require_permission('customers.club_manage')
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def manage_programs(request):
    from django.forms import modelformset_factory
    ProgramSet = modelformset_factory(LoanProgram, form=LoanProgramSettingsForm, extra=1, can_delete=True)
    formset = ProgramSet(request.POST or None, queryset=LoanProgram.objects.all())
    if request.method == 'POST' and formset.is_valid():
        formset.save()
        messages.success(request, 'تنظیمات طرح‌های وام ذخیره شد و ارزیابی‌های بعدی از مقادیر جدید استفاده می‌کنند.')
        return redirect('customers:club_programs')
    if request.method == 'POST':
        messages.error(request, 'تنظیمات طرح‌های وام ذخیره نشد؛ خطاهای مشخص‌شده را اصلاح کنید.')
    return render(request, 'customers/club_program_settings.html', {'formset': formset})
