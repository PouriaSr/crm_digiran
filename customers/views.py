import jdatetime
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.contrib.auth.models import User
from django.http import JsonResponse
from accounts.permissions import require_permission
from .models import Customer, CustomerNote
from .forms import CustomerForm, CustomerNoteForm


# ═══════════════════════════════════════════════════════════════
# کمکی — تاریخ شمسی (۷.۶)
# ═══════════════════════════════════════════════════════════════

def _parse_jalali_date(value):
    """تبدیل تاریخ شمسی به میلادی — None اگه نامعتبر بود"""
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


# ═══════════════════════════════════════════════════════════════
# کمکی — نمایش هشدار تکراری‌ها (۷.۵)
# ═══════════════════════════════════════════════════════════════

def _add_duplicate_warnings(request, form):
    """
    بعد از ذخیره‌ی موفق، هشدار مشتری‌های تکراری رو نشون بده.
    (نه بلاک سخت — فقط اطلاع‌رسانی به کاربر)
    """
    warnings = getattr(form, 'duplicate_warnings', [])
    if not warnings:
        return

    seen = set()
    for warn in warnings:
        dup = warn['customer']
        key = (warn['field'], dup.pk)
        if key in seen:
            continue
        seen.add(key)

        label = 'شماره تماس' if warn['field'] == 'mobile' else 'کد ملی'
        messages.warning(
            request,
            f'⚠️ هشدار: مشتری دیگری با همین {label} وجود دارد — '
            f'«{dup.name}» (شناسه {dup.pk}). '
            f'در صورت نیاز، رکورد تکراری را بررسی و ادغام کنید.'
        )


# ═══════════════════════════════════════════════════════════════
# مشتریان
# ═══════════════════════════════════════════════════════════════

@login_required
@require_permission('customers.view')
def customer_list(request):
    customers = Customer.objects.select_related('assigned_to', 'created_by').all()

    search = request.GET.get('q', '').strip()
    if search:
        customers = customers.filter(
            Q(name__icontains=search) |
            Q(mobile__icontains=search) |
            Q(email__icontains=search) |
            Q(national_id__icontains=search)
        )

    status = request.GET.get('status', '').strip()
    if status:
        customers = customers.filter(status=status)

    source = request.GET.get('source', '').strip()
    if source:
        customers = customers.filter(source=source)

    employee = request.GET.get('employee', '').strip()
    if employee:
        customers = customers.filter(assigned_to_id=employee)

    # ⭐ ۷.۶ — بازه‌ی تاریخ ثبت
    from_date_str = request.GET.get('from_date', '').strip()
    to_date_str = request.GET.get('to_date', '').strip()
    from_date = _parse_jalali_date(from_date_str)
    to_date = _parse_jalali_date(to_date_str)
    if from_date:
        customers = customers.filter(created_at__date__gte=from_date)
    if to_date:
        customers = customers.filter(created_at__date__lte=to_date)

    # ⭐ ۷.۶ — فیلتر داشتن/نداشتن فاکتور
    has_invoice = request.GET.get('has_invoice', '').strip()
    if has_invoice == 'yes':
        customers = customers.filter(invoices__isnull=False).distinct()
    elif has_invoice == 'no':
        customers = customers.filter(invoices__isnull=True)

    has_filters = any([
        search, status, source, employee,
        from_date_str, to_date_str, has_invoice,
    ])

    total = Customer.objects.count()
    leads = Customer.objects.filter(status='lead').count()
    actives = Customer.objects.filter(status='active').count()

    paginator = Paginator(customers, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    employees = User.objects.filter(customers__isnull=False).distinct()

    context = {
        'page_obj': page_obj,
        'total': total,
        'leads': leads,
        'actives': actives,
        'search': search,
        'current_status': status,
        'current_source': source,
        'current_employee': employee,
        'from_date': from_date_str,
        'to_date': to_date_str,
        'current_has_invoice': has_invoice,
        'has_filters': has_filters,
        'filtered_count': customers.count() if has_filters else None,
        'employees': employees,
        'status_choices': Customer.STATUS_CHOICES,
        'source_choices': Customer.SOURCE_CHOICES,
    }
    return render(request, 'customers/list.html', context)


@login_required
@require_permission('customers.view')
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    calls = customer.calls.select_related('called_by').order_by('-call_date')[:10]
    invoices = customer.invoices.order_by('-created_at')[:10]

    paid_count = customer.invoices.filter(status='paid').count()
    issued_count = customer.invoices.filter(status='issued').count()

    total_purchase = customer.invoices.filter(
        status__in=['issued', 'paid']
    ).aggregate(s=Sum('total'))['s'] or 0

    calls_count = customer.calls.count()
    notes = customer.notes_new.select_related('created_by').all()

    context = {
        'customer': customer,
        'calls': calls,
        'invoices': invoices,
        'notes': notes,
        'calls_count': calls_count,
        'invoices_count': paid_count + issued_count,
        'paid_count': paid_count,
        'issued_count': issued_count,
        'total_purchase': total_purchase,
    }
    return render(request, 'customers/detail.html', context)


@login_required
@require_permission('customers.add')
def customer_create(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.created_by = request.user
            customer.save()
            messages.success(request, f'مشتری «{customer.name}» با موفقیت اضافه شد.')
            _add_duplicate_warnings(request, form)
            return redirect('customers:detail', pk=customer.pk)
    else:
        form = CustomerForm()

    return render(request, 'customers/form.html', {
        'form': form,
        'title': 'افزودن مشتری جدید',
        'submit_label': 'ذخیره مشتری',
    })


@login_required
@require_permission('customers.edit')
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, 'اطلاعات مشتری به‌روزرسانی شد.')
            _add_duplicate_warnings(request, form)
            return redirect('customers:detail', pk=customer.pk)
    else:
        form = CustomerForm(instance=customer)

    return render(request, 'customers/form.html', {
        'form': form,
        'title': f'ویرایش مشتری: {customer.name}',
        'submit_label': 'ذخیره تغییرات',
        'customer': customer,
    })


# ═══════════════════════════════════════════════════════════════
# یادداشت‌های مشتری
# ═══════════════════════════════════════════════════════════════

@login_required
@require_permission('customers.edit')
def note_create(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        form = CustomerNoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.customer = customer
            note.created_by = request.user
            note.save()

            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'note_id': note.pk,
                    'text': note.text,
                    'author': note.author_name,
                    'created_at': note.created_at.strftime('%Y/%m/%d %H:%M'),
                    'is_pinned': note.is_pinned,
                    'message': 'یادداشت ثبت شد.',
                })

            messages.success(request, 'یادداشت ثبت شد.')
            return redirect('customers:detail', pk=customer.pk)

        if is_ajax:
            return JsonResponse({
                'success': False,
                'error': 'متن یادداشت نمی‌تواند خالی باشد.',
            }, status=400)

    return redirect('customers:detail', pk=customer.pk)


@login_required
@require_permission('customers.edit')
def note_edit(request, pk, note_pk):
    customer = get_object_or_404(Customer, pk=pk)
    note = get_object_or_404(CustomerNote, pk=note_pk, customer=customer)

    if not note.can_edit(request.user):
        messages.error(request, 'شما اجازه‌ی ویرایش این یادداشت را ندارید.')
        return redirect('customers:detail', pk=customer.pk)

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        form = CustomerNoteForm(request.POST, instance=note)
        if form.is_valid():
            form.save()

            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'text': note.text,
                    'is_pinned': note.is_pinned,
                    'message': 'یادداشت ویرایش شد.',
                })

            messages.success(request, 'یادداشت ویرایش شد.')
            return redirect('customers:detail', pk=customer.pk)

    return redirect('customers:detail', pk=customer.pk)


@login_required
@require_permission('customers.edit')
def note_delete(request, pk, note_pk):
    customer = get_object_or_404(Customer, pk=pk)
    note = get_object_or_404(CustomerNote, pk=note_pk, customer=customer)

    if not note.can_edit(request.user):
        messages.error(request, 'شما اجازه‌ی حذف این یادداشت را ندارید.')
        return redirect('customers:detail', pk=customer.pk)

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        note.delete()

        if is_ajax:
            return JsonResponse({'success': True, 'message': 'یادداشت حذف شد.'})

        messages.success(request, 'یادداشت حذف شد.')
        return redirect('customers:detail', pk=customer.pk)

    return redirect('customers:detail', pk=customer.pk)


@login_required
@require_permission('customers.edit')
def note_toggle_pin(request, pk, note_pk):
    customer = get_object_or_404(Customer, pk=pk)
    note = get_object_or_404(CustomerNote, pk=note_pk, customer=customer)

    if not note.can_edit(request.user):
        return JsonResponse({'success': False, 'error': 'دسترسی ندارید.'}, status=403)

    note.is_pinned = not note.is_pinned
    note.save(update_fields=['is_pinned', 'updated_at'])

    return JsonResponse({
        'success': True,
        'is_pinned': note.is_pinned,
    })