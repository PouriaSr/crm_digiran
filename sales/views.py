import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from products.models import Product
from accounts.permissions import require_permission
from .models import Invoice, InvoiceItem
from .forms import InvoiceForm, InvoiceItemFormSet


# ═════════════════════════════════════════════════
# ثابت‌های مدیریت موجودی
# ═════════════════════════════════════════════════
DEDUCTING_STATUSES = ('issued', 'paid')


# ═════════════════════════════════════════════════
# توابع کمکی
# ═════════════════════════════════════════════════
def _products_prices_dict():
    """دیکشنری قیمت محصولات برای autofill در فرم فاکتور"""
    return {
        str(pk): float(price)
        for pk, price in Product.objects.values_list('id', 'price')
    }


def _apply_invoice_stock(invoice, user):
    """
    کاهش موجودی برای همه‌ی اقلام فاکتور.
    اگر موجودی هر کالایی کافی نباشد ValueError می‌دهد.
    باید داخل یک transaction.atomic صدا زده شود.
    """
    for item in invoice.items.select_related('product'):
        item.product.change_stock(
            -item.quantity,
            movement_type='out',
            user=user,
            reference_type='invoice',
            reference_id=invoice.pk,
            reference_note=invoice.number,
        )


def _reverse_invoice_stock(invoice, user):
    """
    برگرداندن موجودی همه‌ی اقلام فاکتور.
    برای لغو، ویرایش یا حذف فاکتور استفاده می‌شود.
    """
    for item in invoice.items.select_related('product'):
        item.product.change_stock(
            +item.quantity,
            movement_type='cancel',
            user=user,
            reference_type='invoice',
            reference_id=invoice.pk,
            reference_note=f'برگشت {invoice.number}',
        )


# ═════════════════════════════════════════════════
# فهرست و جزئیات
# ═════════════════════════════════════════════════
@login_required
@require_permission('invoices.view')
def invoice_list(request):
    invoices = Invoice.objects.select_related('customer', 'created_by').all()

    search = request.GET.get('q', '').strip()
    if search:
        invoices = invoices.filter(
            Q(number__icontains=search) |
            Q(customer__name__icontains=search) |
            Q(customer__mobile__icontains=search)
        )

    status = request.GET.get('status', '')
    if status:
        invoices = invoices.filter(status=status)

    payment_type = request.GET.get('payment_type', '')
    if payment_type:
        invoices = invoices.filter(payment_type=payment_type)

    all_invoices = Invoice.objects.all()
    stats = {
        'total': all_invoices.count(),
        'draft': all_invoices.filter(status='draft').count(),
        'issued': all_invoices.filter(status='issued').count(),
        'paid': all_invoices.filter(status='paid').count(),
        'total_amount': all_invoices.filter(
            status__in=DEDUCTING_STATUSES
        ).aggregate(s=Sum('total'))['s'] or 0,
    }

    paginator = Paginator(invoices, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'page_obj': page_obj,
        'stats': stats,
        'search': search,
        'current_status': status,
        'current_payment': payment_type,
        'status_choices': Invoice.STATUS_CHOICES,
        'payment_choices': Invoice.PAYMENT_TYPE_CHOICES,
    }
    return render(request, 'sales/list.html', context)


@login_required
@require_permission('invoices.view')
def invoice_detail(request, pk):
    invoice = get_object_or_404(
        Invoice.objects
        .select_related('customer', 'created_by')
        .prefetch_related('logs__user'),
        pk=pk,
    )
    items = invoice.items.select_related('product')
    return render(request, 'sales/detail.html', {
        'invoice': invoice,
        'items': items,
    })


# ═════════════════════════════════════════════════
# ایجاد فاکتور
# ═════════════════════════════════════════════════
@login_required
@require_permission('invoices.add')
def invoice_create(request):
    initial = {}
    customer_id = request.GET.get('customer')
    if customer_id:
        initial['customer'] = customer_id

    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        formset = InvoiceItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    invoice = form.save(commit=False)
                    invoice.created_by = request.user
                    invoice.save()

                    formset.instance = invoice
                    formset.save()
                    # ⭐ signal post_save روی InvoiceItem مبالغ رو خودکار حساب می‌کنه

                    # ⭐ کاهش موجودی اگه فاکتور در وضعیت صادرشده/پرداخت‌شده باشه
                    if invoice.status in DEDUCTING_STATUSES:
                        _apply_invoice_stock(invoice, request.user)

                messages.success(request, f'فاکتور «{invoice.number}» با موفقیت ثبت شد.')
                return redirect('sales:detail', pk=invoice.pk)
            except ValueError as e:
                messages.error(request, f'خطا در موجودی: {e}')
    else:
        form = InvoiceForm(initial=initial)
        formset = InvoiceItemFormSet()

    return render(request, 'sales/form.html', {
        'form': form,
        'formset': formset,
        'title': 'صدور فاکتور جدید',
        'submit_label': 'صدور فاکتور',
        'products_prices': _products_prices_dict(),
    })


# ═════════════════════════════════════════════════
# ویرایش فاکتور
# ═════════════════════════════════════════════════
@login_required
@require_permission('invoices.edit')
def invoice_edit(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)

    if request.method == 'POST':
        old_status = invoice.status
        form = InvoiceForm(request.POST, instance=invoice)
        formset = InvoiceItemFormSet(request.POST, instance=invoice)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # ⭐ ۱. اگه قبلاً کم شده بود، اول برگردون
                    if old_status in DEDUCTING_STATUSES:
                        _reverse_invoice_stock(invoice, request.user)

                    # ⭐ ۲. حالا فرم رو ذخیره کن
                    invoice = form.save()
                    formset.save()
                    # ⭐ signal خودش مبالغ رو حساب می‌کنه

                    # ⭐ ۳. اگه وضعیت جدید باید کم کنه، اعمال کن
                    if invoice.status in DEDUCTING_STATUSES:
                        _apply_invoice_stock(invoice, request.user)

                messages.success(request, 'فاکتور به‌روزرسانی شد.')
                return redirect('sales:detail', pk=invoice.pk)
            except ValueError as e:
                messages.error(request, f'خطا در موجودی: {e}')
    else:
        form = InvoiceForm(instance=invoice)
        formset = InvoiceItemFormSet(instance=invoice)

    return render(request, 'sales/form.html', {
        'form': form,
        'formset': formset,
        'title': f'ویرایش فاکتور {invoice.number}',
        'submit_label': 'ذخیره تغییرات',
        'invoice': invoice,
        'products_prices': _products_prices_dict(),
    })


# ═════════════════════════════════════════════════
# حذف فاکتور
# ═════════════════════════════════════════════════
@login_required
@require_permission('invoices.delete')
def invoice_delete(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                # ⭐ اگه فاکتور در انبار تاثیر داشته، برگردون
                if invoice.status in DEDUCTING_STATUSES:
                    _reverse_invoice_stock(invoice, request.user)

                number = invoice.number
                invoice.delete()

            messages.success(request, f'فاکتور «{number}» حذف شد و موجودی برگشت.')
            return redirect('sales:list')
        except Exception as e:
            messages.error(request, f'خطا در حذف فاکتور: {e}')
            return redirect('sales:detail', pk=pk)

    return render(request, 'sales/confirm_delete.html', {'invoice': invoice})


# ═════════════════════════════════════════════════
# چاپ فاکتور
# ═════════════════════════════════════════════════
@login_required
@require_permission('invoices.print')
def invoice_print(request, pk):
    """نسخه چاپی فاکتور"""
    from django.conf import settings

    invoice = get_object_or_404(
        Invoice.objects.select_related('customer', 'created_by'),
        pk=pk
    )
    items = invoice.items.select_related('product')

    context = {
        'invoice': invoice,
        'items': items,
        'company': settings.COMPANY_INFO,
        'print_date': timezone.now(),
    }
    return render(request, 'sales/print.html', context)