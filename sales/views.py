from crm.numerals import digit_contains
import json
import jdatetime
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.contrib.auth.models import User
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

def _parse_jalali_date(value):
    """تبدیل تاریخ شمسی به میلادی (۷.۶)"""
    if not value:
        return None
    try:
        persian = '۰۱۲۳۴۵۶۷۸۹'
        arabic = '٠١٢٣٤٥٦٧٨٩'
        for i, (p, a) in enumerate(zip(persian, arabic)):
            value = value.replace(p, str(i)).replace(a, str(i))
        value = value.replace('-', '/').replace('.', '/')
        if ' ' in value:
            value = value.split(' ', 1)[0]
        y, m, d = map(int, value.split('/'))
        return jdatetime.date(y, m, d).togregorian()
    except (ValueError, AttributeError):
        return None


def _get_employee_choices():
    """کاربران فعال برای dropdown فیلتر"""
    return User.objects.filter(
        is_active=True,
        is_staff=True,
    ).order_by('first_name', 'last_name', 'username')


def _products_data():
    """
    لیست کالاهای فعال با نام + کد + قیمت — برای autocomplete (۷.۱۰).
    سبک و cache-friendly.
    """
    return [
        {
            'id': p.pk,
            'name': p.name,
            'code': p.code,
            'price': float(p.price),
        }
        for p in Product.objects.only('id', 'name', 'code', 'price')
    ]


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
# فیلترهای پیشرفته (۷.۶)
# ═════════════════════════════════════════════════

def _apply_invoice_filters(qs, request):
    """اعمال همه‌ی فیلترها روی queryset فاکتورها — برمی‌گردونه (qs, filters_dict)"""
    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(
            digit_contains('number', search) |
            digit_contains('customer__name', search) |
            digit_contains('customer__mobile', search)
        )

    status = request.GET.get('status', '').strip()
    if status:
        qs = qs.filter(status=status)

    payment_type = request.GET.get('payment_type', '').strip()
    if payment_type:
        qs = qs.filter(payment_type=payment_type)

    employee = request.GET.get('employee', '').strip()
    if employee:
        qs = qs.filter(created_by_id=employee)

    from_date_str = request.GET.get('from_date', '').strip()
    to_date_str = request.GET.get('to_date', '').strip()
    from_date = _parse_jalali_date(from_date_str)
    to_date = _parse_jalali_date(to_date_str)
    if from_date:
        qs = qs.filter(issue_date__date__gte=from_date)
    if to_date:
        qs = qs.filter(issue_date__date__lte=to_date)

    amount_min_str = request.GET.get('amount_min', '').strip()
    amount_max_str = request.GET.get('amount_max', '').strip()
    try:
        if amount_min_str:
            qs = qs.filter(total__gte=int(amount_min_str.replace(',', '')))
    except (ValueError, TypeError):
        amount_min_str = ''
    try:
        if amount_max_str:
            qs = qs.filter(total__lte=int(amount_max_str.replace(',', '')))
    except (ValueError, TypeError):
        amount_max_str = ''

    filters = {
        'search': search,
        'current_status': status,
        'current_payment': payment_type,
        'current_employee': employee,
        'from_date': from_date_str,
        'to_date': to_date_str,
        'amount_min': amount_min_str,
        'amount_max': amount_max_str,
    }
    return qs, filters


# ═════════════════════════════════════════════════
# فهرست و جزئیات
# ═════════════════════════════════════════════════
@login_required
@require_permission('invoices.view')
def invoice_list(request):
    qs = Invoice.objects.select_related('customer', 'created_by').all()
    qs, filters = _apply_invoice_filters(qs, request)

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

    has_filters = any([
        filters['search'], filters['current_status'],
        filters['current_payment'], filters['current_employee'],
        filters['from_date'], filters['to_date'],
        filters['amount_min'], filters['amount_max'],
    ])

    filtered_stats = None
    if has_filters:
        filtered_stats = {
            'count': qs.count(),
            'total': qs.aggregate(s=Sum('total'))['s'] or 0,
        }

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'page_obj': page_obj,
        'stats': stats,
        'filtered_stats': filtered_stats,
        'has_filters': has_filters,
        'employees': _get_employee_choices(),
        'status_choices': Invoice.STATUS_CHOICES,
        'payment_choices': Invoice.PAYMENT_TYPE_CHOICES,
        **filters,
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
        'products_data': _products_data(),
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
                    if old_status in DEDUCTING_STATUSES:
                        _reverse_invoice_stock(invoice, request.user)

                    invoice = form.save()
                    formset.save()

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
        'products_data': _products_data(),
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