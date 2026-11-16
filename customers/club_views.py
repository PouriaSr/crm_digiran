from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from accounts.permissions import has_permission, require_permission
from products.models import Product

from .access import can_edit_card
from .club_forms import ClubPaymentForm, ClubSelectionForm, LoanEvaluationForm, LoanProgramSettingsForm
from .club_models import ClubAccount, ClubPayment, LoanEvaluation, LoanProgram
from .club_service import create_payment_schedule, evaluate_case, program_eligibility, purchase_budget
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
            'monthly': item.monthly_installment, 'budget': purchase_budget(item, evaluation.proposed_down_payment),
            'down': item.down_payment, 'guarantee': item.guarantee,
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
    if ClubAccount.objects.filter(customer=rec.customer).exists():
        return JsonResponse({'ok': False, 'message': 'برای این مشتری قبلاً قرارداد باشگاه ثبت شده است.'}, status=409)
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
    if not accepted or product.stock < 1 or product.price > purchase_budget(program, evaluation.proposed_down_payment):
        return JsonResponse({'ok': False, 'message': reason or 'قیمت یا موجودی گوشی از زمان ارزیابی تغییر کرده است.'}, status=409)
    delivery = form.cleaned_data['delivery_type']
    panel_url = 'https://example.com/b2b' if delivery == 'instant' else 'https://example.com/b2c'
    guarantee = ' · '.join(x for x in (program.employment_note, program.guarantee) if x)
    account = ClubAccount.objects.create(
        customer=rec.customer, reception=rec, evaluation=evaluation, contract_number=evaluation.contract_number,
        loan_program=program, product=product, delivery_type=delivery, panel_url=panel_url,
        customer_credit_rank=rec.customer.case.credit_rank,
        guarantor_name=rec.customer.case.guarantor_name,
        guarantor_credit_rank=rec.customer.case.guarantor_credit_rank,
        guarantee_snapshot=guarantee, club_fee=form.cleaned_data.get('club_fee') or 0,
        selected_by=request.user,
    )
    evaluation.status = 'selected'
    evaluation.save(update_fields=['status'])
    LoanEvaluation.objects.filter(reception=rec, status='ready').exclude(pk=evaluation.pk).update(status='expired')
    create_payment_schedule(account)
    from hr.task_automation import sync_club_account
    sync_club_account(account)
    return JsonResponse({'ok': True, 'message': f'قرارداد {account.contract_number} ثبت شد؛ مشتری به باشگاه اضافه شد.',
                         'redirect': f"{reverse('customers:hub')}?tab=club&r={rec.pk}"})


@login_required
@require_permission('customers.club')
@require_POST
@transaction.atomic
def add_payment(request, pk):
    account = get_object_or_404(ClubAccount.objects.select_related('customer'), pk=pk)
    if not has_permission(request.user, 'customers.club_payment') or not can_edit_card(request.user, account.customer):
        raise PermissionDenied('مجوز ثبت پرداخت این مشتری را ندارید.')
    form = ClubPaymentForm(request.POST, request.FILES)
    if form.is_valid():
        payment = form.save(commit=False)
        payment.account, payment.created_by = account, request.user
        payment.save()
        from hr.task_automation import sync_club_payment
        sync_club_payment(payment)
        messages.success(request, 'پرداخت و رسید آن در باشگاه مشتریان ثبت شد.')
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
@require_permission('customers.club_manage')
@require_POST
@transaction.atomic
def manage_programs(request):
    from django.forms import modelformset_factory
    ProgramSet = modelformset_factory(LoanProgram, form=LoanProgramSettingsForm, extra=1, can_delete=True)
    formset = ProgramSet(request.POST, queryset=LoanProgram.objects.all())
    if formset.is_valid():
        formset.save()
        messages.success(request, 'تنظیمات طرح‌های وام ذخیره شد و ارزیابی‌های بعدی از مقادیر جدید استفاده می‌کنند.')
    else:
        messages.error(request, 'تنظیمات طرح‌های وام ذخیره نشد؛ مقادیر الزامی و تکراری را بررسی کنید.')
    return redirect(f"{reverse('customers:hub')}?tab=club&loan_settings=1")
