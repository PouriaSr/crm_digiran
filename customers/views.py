from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.contrib.auth.models import User
from accounts.permissions import require_permission
from .models import Customer
from .forms import CustomerForm


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

    status = request.GET.get('status', '')
    if status:
        customers = customers.filter(status=status)

    source = request.GET.get('source', '')
    if source:
        customers = customers.filter(source=source)

    employee = request.GET.get('employee', '')
    if employee:
        customers = customers.filter(assigned_to_id=employee)

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

    context = {
        'customer': customer,
        'calls': calls,
        'invoices': invoices,
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
            return redirect('customers:detail', pk=customer.pk)
    else:
        form = CustomerForm(instance=customer)

    return render(request, 'customers/form.html', {
        'form': form,
        'title': f'ویرایش مشتری: {customer.name}',
        'submit_label': 'ذخیره تغییرات',
        'customer': customer,
    })