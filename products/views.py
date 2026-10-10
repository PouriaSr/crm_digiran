from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F
from accounts.permissions import require_permission
from .models import Product
from .forms import ProductForm


@login_required
@require_permission('products.view')
def product_list(request):
    products = Product.objects.all()

    # جستجو
    search = request.GET.get('q', '').strip()
    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(code__icontains=search) |
            Q(description__icontains=search)
        )

    # فیلتر دسته
    category = request.GET.get('category', '')
    if category:
        products = products.filter(category=category)

    # فیلتر وضعیت
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        products = products.filter(is_active=True)
    elif status_filter == 'inactive':
        products = products.filter(is_active=False)
    elif status_filter == 'low_stock':
        products = products.filter(stock__lte=F('min_stock'), stock__gt=0)
    elif status_filter == 'out_of_stock':
        products = products.filter(stock=0)

    # ═══ آمار ═══
    all_products = Product.objects.all()
    stats = {
        'total': all_products.count(),
        'active': all_products.filter(is_active=True).count(),
        'low_stock': all_products.filter(stock__lte=F('min_stock'), stock__gt=0).count(),
        'out_of_stock': all_products.filter(stock=0).count(),
    }

    # صفحه‌بندی
    paginator = Paginator(products, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'page_obj': page_obj,
        'stats': stats,
        'search': search,
        'current_category': category,
        'current_status': status_filter,
        'category_choices': Product.CATEGORY_CHOICES,
    }
    return render(request, 'products/list.html', context)


@login_required
@require_permission('products.view')
def product_detail(request, pk):
    from sales.models import InvoiceItem
    product = get_object_or_404(Product, pk=pk)

    # ⭐ آخرین فاکتورهایی که این کالا در آن‌ها بوده
    recent_items = InvoiceItem.objects.filter(
        product=product,
        invoice__status__in=['issued', 'paid']
    ).select_related('invoice', 'invoice__customer').order_by('-invoice__created_at')[:10]

    # ⭐ آمار فروش این کالا
    total_sold = sum(item.quantity for item in InvoiceItem.objects.filter(
        product=product,
        invoice__status__in=['issued', 'paid']
    ))

    total_revenue = sum(
        item.total_price for item in InvoiceItem.objects.filter(
            product=product,
            invoice__status__in=['issued', 'paid']
        )
    )

    invoices_count = recent_items.count() if recent_items else 0

    context = {
        'product': product,
        'recent_items': recent_items,
        'total_sold': total_sold,
        'total_revenue': total_revenue,
        'invoices_count': InvoiceItem.objects.filter(
            product=product,
            invoice__status__in=['issued', 'paid']
        ).values('invoice').distinct().count(),
    }
    return render(request, 'products/detail.html', context)


@login_required
@require_permission('products.add')
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'کالای «{product.name}» اضافه شد.')
            return redirect('products:detail', pk=product.pk)
    else:
        form = ProductForm()

    return render(request, 'products/form.html', {
        'form': form,
        'title': 'افزودن کالای جدید',
        'submit_label': 'ذخیره کالا',
    })


@login_required
@require_permission('products.edit')
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'اطلاعات کالا به‌روزرسانی شد.')
            return redirect('products:detail', pk=product.pk)
    else:
        form = ProductForm(instance=product)

    return render(request, 'products/form.html', {
        'form': form,
        'title': f'ویرایش کالا: {product.name}',
        'submit_label': 'ذخیره تغییرات',
        'product': product,
    })


@login_required
@require_permission('products.delete')
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'کالای «{name}» حذف شد.')
        return redirect('products:list')
    return render(request, 'products/confirm_delete.html', {'product': product})