from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F, Count
from accounts.permissions import require_permission, has_permission
from .models import Product, StockMovement, Category
from .forms import ProductForm, CategoryForm


# ═══════════════════════════════════════════════════════════
# کالاها
# ═══════════════════════════════════════════════════════════

@login_required
@require_permission('products.view')
def product_list(request):
    show_deleted = request.GET.get('show') == 'deleted'
    can_see_deleted = has_permission(request.user, 'products.delete')

    if show_deleted and not can_see_deleted:
        show_deleted = False

    if show_deleted:
        products = Product.all_objects.filter(is_deleted=True).select_related('category')
    else:
        products = Product.objects.select_related('category').all()

    search = request.GET.get('q', '').strip()
    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(code__icontains=search) |
            Q(description__icontains=search)
        )

    category_slug = request.GET.get('category', '')
    if category_slug:
        products = products.filter(category__slug=category_slug)

    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        products = products.filter(is_active=True)
    elif status_filter == 'inactive':
        products = products.filter(is_active=False)
    elif status_filter == 'low_stock':
        products = products.filter(stock__lte=F('min_stock'), stock__gt=0)
    elif status_filter == 'out_of_stock':
        products = products.filter(stock=0)

    # ═══════════════════════════════════════════════════════════
    # بهینه‌سازی N+1: قبلاً ۵ کوئری count جدا → الان ۱ + ۱
    # ═══════════════════════════════════════════════════════════
    stats = Product.objects.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(is_active=True)),
        low_stock=Count('id', filter=Q(stock__lte=F('min_stock'), stock__gt=0)),
        out_of_stock=Count('id', filter=Q(stock=0)),
    )
    stats['deleted'] = Product.all_objects.filter(is_deleted=True).count()

    paginator = Paginator(products, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'page_obj': page_obj,
        'stats': stats,
        'search': search,
        'current_category': category_slug,
        'current_status': status_filter,
        'show_deleted': show_deleted,
        # ═══ بهینه‌سازی N+1: جلوگیری از کوئری per-category در template ═══
        'categories': Category.objects.filter(is_active=True).annotate(
            _products_count=Count('products'),
        ),
    }
    return render(request, 'products/list.html', context)


@login_required
@require_permission('products.view')
def product_detail(request, pk):
    from sales.models import InvoiceItem
    product = get_object_or_404(Product.all_objects, pk=pk)

    # ═══════════════════════════════════════════════════════════
    # بهینه‌سازی N+1: قبلاً ۳ کوئری filter + محاسبه‌ی sum در Python
    # الان: ۱ کوئری برای aggregate + ۱ کوئری برای recent_items
    # ═══════════════════════════════════════════════════════════
    base_qs = InvoiceItem.objects.filter(
        product=product,
        invoice__status__in=['issued', 'paid'],
    )

    recent_items = (
        base_qs
        .select_related('invoice', 'invoice__customer')
        .order_by('-invoice__created_at')[:10]
    )

    totals = base_qs.aggregate(
        total_sold=Sum('quantity'),
        total_revenue=Sum('total_price'),
        invoices_count=Count('invoice', distinct=True),
    )

    context = {
        'product': product,
        'recent_items': recent_items,
        'total_sold': totals['total_sold'] or 0,
        'total_revenue': totals['total_revenue'] or 0,
        'invoices_count': totals['invoices_count'] or 0,
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
    product = get_object_or_404(Product.objects, pk=pk)
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
    product = get_object_or_404(Product.objects, pk=pk)

    if request.method == 'POST':
        name = product.name
        was_used = product.is_used
        product.delete()

        if was_used:
            messages.warning(
                request,
                f'کالای «{name}» حذف نرم شد. '
                'چون در فاکتور یا انبار استفاده شده، اطلاعاتش حفظ می‌شود.'
            )
        else:
            messages.success(request, f'کالای «{name}» حذف شد.')
        return redirect('products:list')

    return render(request, 'products/confirm_delete.html', {
        'product': product,
        'is_used': product.is_used,
    })


@login_required
@require_permission('products.delete')
def product_restore(request, pk):
    product = get_object_or_404(Product.all_objects, pk=pk, is_deleted=True)

    if request.method == 'POST':
        product.restore()
        messages.success(request, f'کالای «{product.name}» بازگردانده شد.')
        return redirect('products:detail', pk=product.pk)

    return render(request, 'products/restore.html', {'product': product})


# ═══════════════════════════════════════════════════════════
# دسته‌بندی‌ها
# ═══════════════════════════════════════════════════════════

@login_required
@require_permission('categories.view')
def category_list(request):
    categories = Category.objects.all().order_by('order', 'name')

    search = request.GET.get('q', '').strip()
    if search:
        categories = categories.filter(
            Q(name__icontains=search) |
            Q(slug__icontains=search) |
            Q(description__icontains=search)
        )

    status = request.GET.get('status', '')
    if status == 'active':
        categories = categories.filter(is_active=True)
    elif status == 'inactive':
        categories = categories.filter(is_active=False)

    # ═══════════════════════════════════════════════════════════
    # بهینه‌سازی N+1: یک annotation برای همه‌ی products_count
    # (بدون این خط، هر ردیف یک کوئری COUNT جدا می‌زنه)
    # ═══════════════════════════════════════════════════════════
    categories = categories.annotate(_products_count=Count('products'))

    stats = {
        'total': Category.objects.count(),
        'active': Category.objects.filter(is_active=True).count(),
        'inactive': Category.objects.filter(is_active=False).count(),
    }

    context = {
        'categories': categories,
        'stats': stats,
        'search': search,
        'current_status': status,
    }
    return render(request, 'products/category_list.html', context)


@login_required
@require_permission('categories.manage')
def category_create(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'دسته‌بندی «{category.name}» اضافه شد.')
            return redirect('products:category_list')
    else:
        last = Category.objects.order_by('-order').first()
        initial = {'order': (last.order + 1) if last else 1}
        form = CategoryForm(initial=initial)

    return render(request, 'products/category_form.html', {
        'form': form,
        'title': 'افزودن دسته‌بندی جدید',
        'submit_label': 'ذخیره',
        'is_create': True,
    })


@login_required
@require_permission('categories.manage')
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)

    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'دسته‌بندی به‌روزرسانی شد.')
            return redirect('products:category_list')
    else:
        form = CategoryForm(instance=category)

    return render(request, 'products/category_form.html', {
        'form': form,
        'title': f'ویرایش: {category.name}',
        'submit_label': 'ذخیره تغییرات',
        'is_create': False,
        'category': category,
    })


@login_required
@require_permission('categories.manage')
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    products_count = category.products_count

    if request.method == 'POST':
        if products_count > 0:
            messages.error(
                request,
                f'این دسته دارای {products_count} کالا است و قابل حذف نیست. '
                'ابتدا کالاها را به دسته‌ی دیگری منتقل کنید یا دسته را غیرفعال کنید.'
            )
            return redirect('products:category_list')

        name = category.name
        category.delete()
        messages.success(request, f'دسته‌بندی «{name}» حذف شد.')
        return redirect('products:category_list')

    return render(request, 'products/category_confirm_delete.html', {
        'category': category,
        'products_count': products_count,
    })


# ═══════════════════════════════════════════════════════════
# ورود از Excel — فاز ۷.۸
# ═══════════════════════════════════════════════════════════
import uuid
from django.core.cache import cache
from django.http import HttpResponse

from crm.excel_utils import ExcelImportError
from .excel_import import (
    build_product_template,
    parse_product_excel,
    save_valid_products,
)


_CACHE_PREFIX = 'product_excel_import'
_CACHE_TIMEOUT = 30 * 60
_MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB


@login_required
@require_permission('products.add')
def product_excel_import(request):
    """آپلود فایل Excel کالاها"""
    if request.method == 'POST':
        file = request.FILES.get('excel_file')
        if not file:
            messages.error(request, 'فایلی انتخاب نشده است.')
            return redirect('products:excel_import')

        if not file.name.lower().endswith(('.xlsx', '.xlsm')):
            messages.error(request, 'فقط فایل‌های Excel (xlsx) پشتیبانی می‌شوند.')
            return redirect('products:excel_import')

        if file.size > _MAX_UPLOAD_SIZE:
            messages.error(request, 'حجم فایل نباید بیش از ۵ مگابایت باشد.')
            return redirect('products:excel_import')

        try:
            result = parse_product_excel(file)
        except ExcelImportError as e:
            messages.error(request, str(e))
            return redirect('products:excel_import')

        if result['header_errors']:
            messages.error(
                request,
                'ستون‌های الزامی زیر در فایل یافت نشد: '
                + '، '.join(result['header_errors']),
            )
            return redirect('products:excel_import')

        if not result['rows']:
            messages.warning(request, 'فایل خالی است یا سطری برای پردازش ندارد.')
            return redirect('products:excel_import')

        token = str(uuid.uuid4())
        cache.set(f'{_CACHE_PREFIX}:{token}', result, _CACHE_TIMEOUT)
        return redirect('products:excel_preview', token=token)

    return render(request, 'products/excel_import.html')


@login_required
@require_permission('products.add')
def product_excel_preview(request, token):
    """پیش‌نمایش و تأیید نهایی"""
    result = cache.get(f'{_CACHE_PREFIX}:{token}')
    if not result:
        messages.error(request, 'نشست منقضی شده. لطفاً فایل را دوباره بارگذاری کنید.')
        return redirect('products:excel_import')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'cancel':
            cache.delete(f'{_CACHE_PREFIX}:{token}')
            messages.info(request, 'ورود داده لغو شد.')
            return redirect('products:list')

        if action == 'confirm':
            save_result = save_valid_products(result['rows'], request.user)
            cache.delete(f'{_CACHE_PREFIX}:{token}')

            if save_result['created']:
                messages.success(
                    request,
                    f"{save_result['created']} کالا با موفقیت اضافه شد.",
                )
            if save_result['skipped']:
                messages.warning(
                    request,
                    f"{save_result['skipped']} ردیف نامعتبر یا خطادار نادیده گرفته شد.",
                )
            for err in save_result['errors'][:5]:
                messages.error(request, err)

            return redirect('products:list')

    return render(request, 'products/excel_preview.html', {
        'result': result,
        'token': token,
    })


@login_required
@require_permission('products.add')
def product_excel_template(request):
    """دانلود قالب Excel"""
    content = build_product_template()
    response = HttpResponse(
        content,
        content_type=(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ),
    )
    response['Content-Disposition'] = 'attachment; filename="products-template.xlsx"'
    return response