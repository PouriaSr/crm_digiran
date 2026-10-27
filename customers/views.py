import jdatetime
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from accounts.permissions import require_permission, get_user_role, ROLE_ADMIN, has_permission
from .access import can_edit_card, is_card_manager
from django.core.exceptions import PermissionDenied
from .models import Customer, CustomerNote
from .forms import CustomerForm, CustomerNoteForm, HubCallForm


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
# کمکی — نمایش هشدار تکراری‌ها (ارتقاءیافته)
# ═══════════════════════════════════════════════════════════════

def _add_duplicate_warnings(request, form):
    """
    نمایش هشدارهای مشابهت (نه exact) پس از save موفق.
    exact matchها به‌عنوان ValidationError در فرم بلاک می‌شن.
    """
    from crm.duplicate_check import show_duplicate_warnings
    show_duplicate_warnings(request, form)


# ═══════════════════════════════════════════════════════════════
# مشتریان
# ═══════════════════════════════════════════════════════════════


@login_required
@require_permission('customers.view')
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    # ⭐ فقط کاربرانی که invoices.view دارند، اطلاعات فاکتور را می‌بینند
    can_view_invoices = has_permission(request.user, 'invoices.view')

    calls = customer.calls.select_related('called_by').order_by('-call_date')[:10]

    if can_view_invoices:
        invoices = customer.invoices.order_by('-created_at')[:10]
        paid_count = customer.invoices.filter(status='paid').count()
        issued_count = customer.invoices.filter(status='issued').count()
        total_purchase = customer.invoices.filter(
            status__in=['issued', 'paid']
        ).aggregate(s=Sum('total'))['s'] or 0
    else:
        invoices = customer.invoices.none()
        paid_count = 0
        issued_count = 0
        total_purchase = 0

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
        'can_view_invoices': can_view_invoices,
        'show_full_profile': has_permission(request.user, 'customers.profile_full'),
        'call_form': HubCallForm(user=request.user),
    }
    return render(request, 'customers/detail.html', context)


@login_required
@require_permission('customers.add')
def customer_create(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST, for_create=True)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.created_by = request.user
            if not getattr(customer, 'status', None):
                customer.status = 'lead'
            if not customer.assigned_to_id:
                customer.assigned_to = request.user
            customer.save()
            messages.success(request, f'مشتری «{customer.name}» با موفقیت اضافه شد.')
            _add_duplicate_warnings(request, form)
            
            list_url = f"{reverse('customers:hub')}?tab=info"

            if request.headers.get('HX-Request') or request.GET.get('is_modal') == '1':
                from django.http import HttpResponse
                # HX-Redirect: خود HTMX مرورگر را به لیست مشتریان می‌برد
                # (به رویداد جاوااسکریپت وابسته نیست) و پیام موفقیت دیده می‌شود
                return HttpResponse(status=204, headers={
                    'HX-Redirect': list_url,
                    'HX-Trigger': 'closeModal',
                })

            return redirect(list_url)
    else:
        initial = {'assigned_to': request.user}
        mobile_q = request.GET.get('mobile')
        if mobile_q:
            initial['mobile'] = mobile_q
        name_q = request.GET.get('name')
        if name_q:
            initial['name'] = name_q
        form = CustomerForm(initial=initial, for_create=True)

    if request.headers.get('HX-Request') or request.GET.get('is_modal') == '1':
        return render(request, 'customers/form_modal.html', {
            'form': form,
            'title': 'افزودن مشتری جدید',
            'submit_label': 'ذخیره مشتری',
        })

    return render(request, 'customers/form.html', {
        'form': form,
        'title': 'افزودن مشتری جدید',
        'submit_label': 'ذخیره مشتری',
    })

@login_required
def customer_edit(request, pk):
    full = has_permission(request.user, 'customers.profile_full')
    customer = get_object_or_404(Customer, pk=pk)
    if not can_edit_card(request.user, customer):
        raise PermissionDenied('ویرایش فقط برای کارشناس مسئول کارت، سرپرست و ادمین مجاز است.')
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer, limited=not full)
        if not is_card_manager(request.user):
            form.fields.pop('assigned_to', None)
        if form.is_valid():
            form.save()
            messages.success(request, 'اطلاعات مشتری به‌روزرسانی شد.')
            _add_duplicate_warnings(request, form)

            if request.headers.get('HX-Request') or request.GET.get('is_modal') == '1':
                from django.http import HttpResponse
                return HttpResponse(status=204, headers={
                    'HX-Redirect': f"{reverse('customers:hub')}?tab=info",
                    'HX-Trigger': 'closeModal',
                })

            return redirect('customers:detail', pk=customer.pk)
    else:
        form = CustomerForm(instance=customer, limited=not full)
        if not is_card_manager(request.user):
            form.fields.pop('assigned_to', None)

    is_modal = request.headers.get('HX-Request') or request.GET.get('is_modal') == '1'
    return render(request, 'customers/form_modal.html' if is_modal else 'customers/form.html', {
        'form': form,
        'title': 'ویرایش مشتری',
        'submit_label': 'ذخیره تغییرات',
        'customer': customer,
    })


# ═══════════════════════════════════════════════════════════════
# غیرفعال‌سازی و بازگردانی مشتری
# ═══════════════════════════════════════════════════════════════

@login_required
@require_POST
def customer_deactivate(request, pk):
    # مجوز از ماتریس پیشرفته خوانده می‌شود (customers.delete)
    if not has_permission(request.user, 'customers.delete'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("برای غیرفعال‌سازی مشتری مجوز customers.delete لازم است.")
    customer = get_object_or_404(Customer.objects, pk=pk)
    name = customer.name
    customer.delete()
    messages.success(request, f'مشتری «{name}» غیرفعال شد و به لیست غیرفعال‌ها منتقل شد.')
    return redirect('/customers/hub/?tab=info')


@login_required
def customer_restore(request, pk):
    if not has_permission(request.user, 'customers.delete'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("برای بازگردانی مشتری مجوز customers.delete لازم است.")

    customer = get_object_or_404(Customer.all_objects, pk=pk, is_deleted=True)

    def find_conflict(c):
        if c.mobile:
            other = (
                Customer.objects.filter(mobile=c.mobile)
                .exclude(pk=c.pk)
                .first()
            )
            if other:
                return other, "شماره تماس"
        name = (c.name or "").strip()
        if name:
            other = (
                Customer.objects.filter(name__iexact=name)
                .exclude(pk=c.pk)
                .first()
            )
            if other:
                return other, "نام"
        return None, None

    conflict, reason = find_conflict(customer)

    if conflict:
        messages.warning(
            request,
            f'بازگردانی انجام نشد: مشتری فعال «{conflict.name}» با همین {reason} از قبل وجود دارد. صفحه ویرایش همان مشتری باز شد.'
        )
        return redirect('customers:edit', pk=conflict.pk)

    if request.method == 'POST':
        customer.restore()
        messages.success(request, f'مشتری «{customer.name}» با موفقیت بازگردانی شد.')
        return redirect('/customers/hub/?tab=info')

    return render(request, 'customers/restore.html', {'customer': customer})



@login_required
def customer_inactive_list(request):

    if not has_permission(request.user, 'customers.view'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("برای مشاهده لیست غیرفعال‌ها مجوز customers.view لازم است.")
    customers = (
        Customer.all_objects
        .filter(is_deleted=True)
        .select_related('assigned_to', 'created_by')
    )
    search = request.GET.get('q', '').strip()
    if search:
        customers = customers.filter(
            Q(name__icontains=search) |
            Q(mobile__icontains=search) |
            Q(email__icontains=search) |
            Q(national_id__icontains=search)
        )
    paginator = Paginator(customers, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'customers/inactive_list.html', {
        'page_obj': page_obj,
        'search': search,
        'total_inactive': Customer.all_objects.filter(is_deleted=True).count(),
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
@require_POST
def note_toggle_pin(request, pk, note_pk):
    """سنجاق/لغو سنجاق یادداشت — فقط POST (جلوگیری از CSRF)"""
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


# ═══════════════════════════════════════════════════════════════
# ورود از Excel — فاز ۷.۸
# ═══════════════════════════════════════════════════════════════
import uuid
from django.core.cache import cache
from django.http import HttpResponse

from crm.excel_utils import ExcelImportError
from .excel_import import (
    build_customer_template,
    parse_customer_excel,
    save_valid_customers,
)


_CACHE_PREFIX = 'customer_excel_import'
_CACHE_TIMEOUT = 30 * 60
_MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB


@login_required
@require_permission('customers.add')
def customer_excel_import(request):
    """آپلود فایل Excel مشتریان"""
    if request.method == 'POST':
        file = request.FILES.get('excel_file')
        if not file:
            messages.error(request, 'فایلی انتخاب نشده است.')
            return redirect('customers:excel_import')

        if not file.name.lower().endswith(('.xlsx', '.xlsm')):
            messages.error(request, 'فقط فایل‌های Excel (xlsx) پشتیبانی می‌شوند.')
            return redirect('customers:excel_import')

        if file.size > _MAX_UPLOAD_SIZE:
            messages.error(request, 'حجم فایل نباید بیش از ۵ مگابایت باشد.')
            return redirect('customers:excel_import')

        try:
            result = parse_customer_excel(file)
        except ExcelImportError as e:
            messages.error(request, str(e))
            return redirect('customers:excel_import')

        if result['header_errors']:
            messages.error(
                request,
                'ستون‌های الزامی زیر در فایل یافت نشد: '
                + '، '.join(result['header_errors']),
            )
            return redirect('customers:excel_import')

        if not result['rows']:
            messages.warning(request, 'فایل خالی است یا سطری برای پردازش ندارد.')
            return redirect('customers:excel_import')

        token = str(uuid.uuid4())
        cache.set(f'{_CACHE_PREFIX}:{token}', result, _CACHE_TIMEOUT)
        return redirect('customers:excel_preview', token=token)

    return render(request, 'customers/excel_import.html')


@login_required
@require_permission('customers.add')
def customer_excel_preview(request, token):
    """پیش‌نمایش و تأیید نهایی"""
    result = cache.get(f'{_CACHE_PREFIX}:{token}')
    if not result:
        messages.error(request, 'نشست منقضی شده. لطفاً فایل را دوباره بارگذاری کنید.')
        return redirect('customers:excel_import')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'cancel':
            cache.delete(f'{_CACHE_PREFIX}:{token}')
            messages.info(request, 'ورود داده لغو شد.')
            return redirect('customers:list')

        if action == 'confirm':
            save_result = save_valid_customers(result['rows'], request.user)
            cache.delete(f'{_CACHE_PREFIX}:{token}')

            if save_result['created']:
                messages.success(
                    request,
                    f"{save_result['created']} مشتری با موفقیت اضافه شد.",
                )
            if save_result['skipped']:
                messages.warning(
                    request,
                    f"{save_result['skipped']} ردیف نامعتبر یا خطادار نادیده گرفته شد.",
                )
            for err in save_result['errors'][:5]:
                messages.error(request, err)

            return redirect('customers:list')

    return render(request, 'customers/excel_preview.html', {
        'result': result,
        'token': token,
    })


@login_required
@require_permission('customers.add')
def customer_excel_template(request):
    """دانلود قالب Excel"""
    content = build_customer_template()
    response = HttpResponse(
        content,
        content_type=(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ),
    )
    response['Content-Disposition'] = 'attachment; filename="customers-template.xlsx"'
    return response