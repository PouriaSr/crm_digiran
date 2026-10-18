from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta
from accounts.permissions import require_permission
from .models import Call
from .forms import CallForm


@login_required
@require_permission('calls.view')
def call_list(request):
    calls = Call.objects.select_related('customer', 'called_by').all()

    # ═══ جستجو ═══
    search = request.GET.get('q', '').strip()
    if search:
        calls = calls.filter(
            Q(caller_name__icontains=search) |
            Q(call_number__icontains=search) |
            Q(notes__icontains=search)
        )

    # ═══ فیلتر وضعیت ═══
    status = request.GET.get('status', '')
    if status:
        if status == 'followup':
            calls = calls.filter(status='followup', is_followed_up=False)
        else:
            calls = calls.filter(status=status)

    # ═══ فیلتر نوع ═══
    call_type = request.GET.get('call_type', '')
    if call_type:
        calls = calls.filter(call_type=call_type)

    # ═══ فیلتر هدف ═══
    purpose = request.GET.get('purpose', '')
    if purpose:
        calls = calls.filter(purpose=purpose)

    # ═══ فیلتر کارمند ═══
    employee = request.GET.get('employee', '')
    if employee:
        calls = calls.filter(called_by_id=employee)

    # ═══ فیلتر وضعیت پیگیری ═══
    followup_status = request.GET.get('followup', '')
    today = timezone.now().date() # ⭐ گرفتن تاریخ امروز
    
    if followup_status == 'pending':
        # ⭐ دقیقاً هم‌منطق با سیستم اعلان‌ها (تاریخ پیگیری گذشته یا امروز است و تیک نخورده)
        calls = calls.filter(follow_up_date__lte=today, is_followed_up=False)
    elif followup_status == 'done':
        calls = calls.filter(is_followed_up=True)
    elif followup_status == 'has_date':
        calls = calls.filter(follow_up_date__isnull=False)

    # ═══ آمار کلی ═══
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    stats = {
        'total': Call.objects.count(),
        'today': Call.objects.filter(call_date__date=today).count(),
        'week': Call.objects.filter(call_date__date__gte=week_ago).count(),
        'followup': Call.objects.filter(status='followup', is_followed_up=False).count(),
    }

    # ═══ صفحه‌بندی ═══
    paginator = Paginator(calls, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # ═══ کارمندان برای dropdown ═══
    employees = User.objects.filter(calls__isnull=False).distinct()

    context = {
        'page_obj': page_obj,
        'stats': stats,
        'search': search,
        'current_status': status,
        'current_call_type': call_type,
        'current_purpose': purpose,
        'current_employee': employee,
        'current_followup': followup_status,
        'employees': employees,
        'status_choices': Call.CALL_STATUS_CHOICES,
        'type_choices': Call.CALL_TYPE_CHOICES,
        'purpose_choices': Call.CALL_PURPOSE_CHOICES,
    }
    return render(request, 'calls/list.html', context)


@login_required
@require_permission('calls.view')
def call_detail(request, pk):
    call = get_object_or_404(Call, pk=pk)
    return render(request, 'calls/detail.html', {'call': call})


@login_required
@require_permission('calls.add')
def call_create(request):
    initial = {}
    customer_id = request.GET.get('customer')
    if customer_id:
        try:
            from customers.models import Customer
            customer = Customer.objects.get(pk=customer_id)
            initial['customer'] = customer.pk
            initial['caller_name'] = customer.name
            initial['call_number'] = customer.mobile
        except Customer.DoesNotExist:
            pass

    if request.method == 'POST':
        form = CallForm(request.POST)
        if form.is_valid():
            call = form.save(commit=False)
            call.created_by = request.user
            if not call.called_by:
                call.called_by = request.user
            call.save()
            messages.success(request, f'تماس با «{call.caller_name}» ثبت شد.')
            return redirect('calls:detail', pk=call.pk)
    else:
        form = CallForm(initial=initial)

    return render(request, 'calls/form.html', {
        'form': form,
        'title': 'ثبت تماس جدید',
        'submit_label': 'ذخیره تماس',
    })


@login_required
@require_permission('calls.edit')
def call_edit(request, pk):
    call = get_object_or_404(Call, pk=pk)
    if request.method == 'POST':
        form = CallForm(request.POST, instance=call)
        if form.is_valid():
            form.save()
            messages.success(request, 'اطلاعات تماس به‌روزرسانی شد.')
            return redirect('calls:detail', pk=call.pk)
    else:
        form = CallForm(instance=call)

    return render(request, 'calls/form.html', {
        'form': form,
        'title': f'ویرایش تماس با {call.caller_name}',
        'submit_label': 'ذخیره تغییرات',
        'call': call,
    })


@login_required
@require_permission('calls.delete')
def call_delete(request, pk):
    call = get_object_or_404(Call, pk=pk)
    if request.method == 'POST':
        name = call.caller_name
        call.delete()
        messages.success(request, f'تماس با «{name}» حذف شد.')
        return redirect('calls:list')
    return render(request, 'calls/confirm_delete.html', {'call': call})


@login_required
@require_permission('calls.reassign')
def call_reassign(request, pk):
    """ارجاع تماس به کارمند دیگر — پشتیبانی از AJAX و فرم معمولی"""
    call = get_object_or_404(Call, pk=pk)

    if request.method == 'POST':
        new_user_id = request.POST.get('called_by')
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if not new_user_id:
            if is_ajax:
                return JsonResponse({'success': False, 'error': 'کارمند جدید انتخاب نشده'}, status=400)
            messages.error(request, 'لطفاً یک کارمند انتخاب کنید.')
            return redirect('calls:reassign', pk=pk)

        try:
            new_user = User.objects.get(pk=new_user_id)
        except User.DoesNotExist:
            if is_ajax:
                return JsonResponse({'success': False, 'error': 'کارمند یافت نشد'}, status=404)
            messages.error(request, 'کارمند انتخابی یافت نشد.')
            return redirect('calls:reassign', pk=pk)

        old_user = call.called_by
        call.called_by = new_user
        call.save(update_fields=['called_by', 'updated_at'])

        old_name = '—'
        if old_user:
            old_name = old_user.get_full_name() or old_user.username
        new_name = new_user.get_full_name() or new_user.username

        # ⭐ پاسخ برای AJAX
        if is_ajax:
            return JsonResponse({
                'success': True,
                'new_user_name': new_name,
                'old_user_name': old_name,
                'message': f'تماس از «{old_name}» به «{new_name}» ارجاع شد.'
            })

        # ⭐ پاسخ برای فرم معمولی
        messages.success(request, f'تماس از «{old_name}» به «{new_name}» ارجاع شد.')
        return redirect('calls:detail', pk=call.pk)

    users = User.objects.filter(is_active=True).order_by('first_name', 'username')
    return render(request, 'calls/reassign.html', {
        'call': call,
        'users': users,
    })