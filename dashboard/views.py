import io
import json
import jdatetime
from datetime import datetime, timedelta
from decimal import Decimal

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Count, F, Avg
from django.http import HttpResponse
from django.utils import timezone

from accounts.permissions import require_permission
from customers.models import Customer
from calls.models import Call
from products.models import Product
from sales.models import Invoice, InvoiceItem
from hr.models import Employee, Task


# ═══════════════════════════════════════════
# توابع کمکی
# ═══════════════════════════════════════════

def _to_jalali_month(g_date):
    try:
        j = jdatetime.date.fromgregorian(date=g_date)
        return f"{j.year}/{j.month:02d}"
    except Exception:
        return str(g_date)


def _get_month_range(year, month):
    try:
        start_j = jdatetime.date(year, month, 1)
        start_g = start_j.togregorian()
        if month == 12:
            end_j = jdatetime.date(year + 1, 1, 1)
        else:
            end_j = jdatetime.date(year, month + 1, 1)
        end_g = end_j.togregorian() - timedelta(days=1)
        return start_g, end_g
    except Exception:
        return None, None


def _parse_jalali_date(value):
    """تبدیل رشته تاریخ شمسی به date میلادی"""
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


def _get_dashboard_data(from_date=None, to_date=None):
    """جمع‌آوری تمام داده‌های داشبورد با فیلتر تاریخ"""
    today = timezone.now().date()
    now_j = jdatetime.date.fromgregorian(date=today)

    # ═══ اعمال فیلتر تاریخ روی همه QuerySetها ═══
    invoices_qs = Invoice.objects.filter(status__in=['issued', 'paid'])
    calls_qs = Call.objects.all()
    customers_qs = Customer.objects.all()

    if from_date:
        invoices_qs = invoices_qs.filter(issue_date__gte=from_date)
        calls_qs = calls_qs.filter(call_date__date__gte=from_date)
        customers_qs = customers_qs.filter(created_at__date__gte=from_date)

    if to_date:
        invoices_qs = invoices_qs.filter(issue_date__lte=to_date)
        calls_qs = calls_qs.filter(call_date__date__lte=to_date)
        customers_qs = customers_qs.filter(created_at__date__lte=to_date)

    # ═══ KPI ها ═══
    total_customers = customers_qs.count()
    active_customers = customers_qs.filter(status='active').count()
    lead_customers = customers_qs.filter(status='lead').count()

    total_calls = calls_qs.count()

    # ماه جاری شمسی
    this_month_start, this_month_end = _get_month_range(now_j.year, now_j.month)
    calls_this_month = Call.objects.filter(
        call_date__date__gte=this_month_start,
        call_date__date__lte=this_month_end,
    ).count()

    total_invoices = invoices_qs.count()
    total_sales = invoices_qs.aggregate(s=Sum('total'))['s'] or 0

    # ═══ فروش در بازه انتخابی (اگه فیلتر باشه) یا این ماه (پیش‌فرض) ═══
    if from_date or to_date:
        sales_this_month = total_sales
    else:
        month_start, month_end = _get_month_range(now_j.year, now_j.month)
        sales_this_month = Invoice.objects.filter(
            status__in=['issued', 'paid'],
            issue_date__gte=month_start,
            issue_date__lte=month_end,
        ).aggregate(s=Sum('total'))['s'] or 0

    # ═══ فروش ماه قبل و سال قبل (برای مقایسه) ═══
    prev_year = now_j.year if now_j.month > 1 else now_j.year - 1
    prev_month = now_j.month - 1 if now_j.month > 1 else 12
    prev_start, prev_end = _get_month_range(prev_year, prev_month)
    sales_last_month = Invoice.objects.filter(
        status__in=['issued', 'paid'],
        issue_date__gte=prev_start,
        issue_date__lte=prev_end,
    ).aggregate(s=Sum('total'))['s'] or 0

    last_year_start, last_year_end = _get_month_range(now_j.year - 1, now_j.month)
    sales_last_year = Invoice.objects.filter(
        status__in=['issued', 'paid'],
        issue_date__gte=last_year_start,
        issue_date__lte=last_year_end,
    ).aggregate(s=Sum('total'))['s'] or 0

    # تغییر ماهانه
    if sales_last_month and sales_last_month > 0:
        sales_change = round(
            (float(sales_this_month) - float(sales_last_month))
            / float(sales_last_month) * 100, 1
        )
    else:
        sales_change = 100 if sales_this_month > 0 else 0

    # تغییر سالانه
    if sales_last_year and sales_last_year > 0:
        yearly_change = round(
            (float(sales_this_month) - float(sales_last_year))
            / float(sales_last_year) * 100, 1
        )
    else:
        yearly_change = 100 if sales_this_month > 0 else 0

    # ═══════════════════════════════════════════════════════
    # نمودار فروش ۱۲ ماه اخیر — با اعمال فیلتر
    # ═══════════════════════════════════════════════════════
    sales_data = []
    sales_labels = []
    for i in range(11, -1, -1):
        m = now_j.month - i
        y = now_j.year
        while m <= 0:
            m += 12
            y -= 1

        s_start, s_end = _get_month_range(y, m)
        if s_start is None:
            continue

        if from_date and s_end < from_date:
            continue
        if to_date and s_start > to_date:
            continue

        month_sales = Invoice.objects.filter(
            status__in=['issued', 'paid'],
            issue_date__gte=s_start,
            issue_date__lte=s_end,
        ).aggregate(s=Sum('total'))['s'] or 0

        sales_data.append(float(month_sales))
        sales_labels.append(f"{y}/{m:02d}")

    if not sales_data:
        sales_data = [0]
        sales_labels = ['بدون داده']

    # ═══ توزیع منابع جذب مشتری ═══
    sources_qs = customers_qs.values('source').annotate(
        count=Count('id')
    ).order_by('-count')

    source_labels_map = dict(Customer.SOURCE_CHOICES)
    source_data = []
    source_labels = []
    for item in sources_qs:
        source_labels.append(source_labels_map.get(item['source'], 'سایر'))
        source_data.append(item['count'])

    if not source_data:
        source_data = [0]
        source_labels = ['بدون داده']

    # ═══ توزیع وضعیت مشتریان ═══
    status_qs = customers_qs.values('status').annotate(
        count=Count('id')
    ).order_by('-count')

    status_labels_map = dict(Customer.STATUS_CHOICES)
    status_data = []
    status_labels = []
    for item in status_qs:
        status_labels.append(status_labels_map.get(item['status'], 'سایر'))
        status_data.append(item['count'])

    if not status_data:
        status_data = [0]
        status_labels = ['بدون داده']

    # ═══ توزیع وضعیت تماس‌ها ═══
    call_status_qs = calls_qs.values('status').annotate(
        count=Count('id')
    ).order_by('-count')

    call_status_map = dict(Call.CALL_STATUS_CHOICES)
    call_status_data = []
    call_status_labels = []
    for item in call_status_qs:
        call_status_labels.append(call_status_map.get(item['status'], 'سایر'))
        call_status_data.append(item['count'])

    if not call_status_data:
        call_status_data = [0]
        call_status_labels = ['بدون داده']

    # ═══ پرفروش‌ترین کالاها ═══
    top_products = InvoiceItem.objects.filter(
        invoice__in=invoices_qs
    ).values(name=F('product__name')).annotate(
        total_qty=Sum('quantity'),
        total_revenue=Sum('total_price')
    ).order_by('-total_qty')[:5]

    top_products_list = [
        {
            'name': p['name'],
            'qty': p['total_qty'],
            'revenue': float(p['total_revenue'] or 0),
        }
        for p in top_products
    ]

    # ═══ عملکرد کارمندان ═══
    employee_perf = invoices_qs.filter(
        created_by__isnull=False
    ).values(
        username=F('created_by__username'),
        first_name=F('created_by__first_name'),
        last_name=F('created_by__last_name'),
    ).annotate(
        total_sales=Sum('total'),
        invoice_count=Count('id')
    ).order_by('-total_sales')

    employee_perf_list = []
    for e in employee_perf:
        name = f"{e['first_name'] or ''} {e['last_name'] or ''}".strip()
        if not name:
            name = e['username']
        employee_perf_list.append({
            'name': name,
            'username': e['username'],
            'total_sales': float(e['total_sales'] or 0),
            'invoice_count': e['invoice_count'],
        })

    emp_chart_names = [e['name'] for e in employee_perf_list[:10]]
    emp_chart_values = [e['total_sales'] for e in employee_perf_list[:10]]

    # ═══════════════════════════════════════════════════════
    # قیف فروش — با اعمال فیلتر
    # ═══════════════════════════════════════════════════════
    leads_count = customers_qs.filter(status='lead').count()

    leads_with_calls = Call.objects.filter(
        customer__in=customers_qs.filter(status='lead')
    ).values('customer').distinct().count()

    leads_with_invoice = Invoice.objects.filter(
        customer__in=customers_qs.filter(status='lead')
    ).values('customer').distinct().count()

    paid_leads = Invoice.objects.filter(
        customer__in=customers_qs.filter(status='lead'),
        status='paid'
    ).values('customer').distinct().count()

    funnel_data = {
        'labels': ['لید جدید', 'تماس گرفته', 'فاکتور صادر', 'پرداخت شده'],
        'values': [leads_count, leads_with_calls, leads_with_invoice, paid_leads],
    }

    # ═══════════════════════════════════════════════════════
    # مقایسه فروش — با اعمال فیلتر
    # ═══════════════════════════════════════════════════════
    if from_date or to_date:
        if from_date and to_date:
            range_days = (to_date - from_date).days + 1
            prev_range_end = from_date - timedelta(days=1)
            prev_range_start = prev_range_end - timedelta(days=range_days - 1)

            prev_sales = Invoice.objects.filter(
                status__in=['issued', 'paid'],
                issue_date__gte=prev_range_start,
                issue_date__lte=prev_range_end,
            ).aggregate(s=Sum('total'))['s'] or 0

            compare_data = {
                'labels': ['بازه قبل', 'بازه انتخابی'],
                'values': [float(prev_sales), float(total_sales)],
            }
        else:
            compare_data = {
                'labels': ['بازه انتخابی'],
                'values': [float(total_sales)],
            }
    else:
        compare_data = {
            'labels': ['ماه قبل', 'این ماه', 'سال قبل (همین ماه)'],
            'values': [
                float(sales_last_month),
                float(sales_this_month),
                float(sales_last_year),
            ],
        }

    # ═══ وظایف و مرخصی ═══
    open_tasks = Task.objects.filter(status__in=['pending', 'in_progress']).count()
    overdue_tasks = Task.objects.filter(
        due_date__lt=today
    ).exclude(status__in=['done', 'cancelled']).count()

    pending_leaves = 0
    try:
        from hr.models import LeaveRequest
        pending_leaves = LeaveRequest.objects.filter(status='pending').count()
    except Exception:
        pass

    # ═══ آماده‌سازی JSON امن برای چارت‌ها ═══
    def _json(obj):
        return json.dumps(obj, ensure_ascii=False)

    return {
        'today': now_j.strftime('%Y/%m/%d'),

        'kpis': {
            'total_customers': total_customers,
            'active_customers': active_customers,
            'lead_customers': lead_customers,
            'total_calls': total_calls,
            'calls_this_month': calls_this_month,
            'total_invoices': total_invoices,
            'total_sales': total_sales,
            'sales_this_month': sales_this_month,
            'sales_last_month': sales_last_month,
            'sales_last_year': sales_last_year,
            'sales_change': sales_change,
            'yearly_change': yearly_change,
            'open_tasks': open_tasks,
            'overdue_tasks': overdue_tasks,
            'pending_leaves': pending_leaves,
        },

        # ═══ داده‌های خام (برای Excel) ═══
        'sales_data': sales_data,
        'sales_labels': sales_labels,
        'source_data': source_data,
        'source_labels': source_labels,

        # ═══ JSON امن برای چارت‌ها ═══
        'sales_data_json': _json(sales_data),
        'sales_labels_json': _json(sales_labels),

        'source_data_json': _json(source_data),
        'source_labels_json': _json(source_labels),
        'status_data_json': _json(status_data),
        'status_labels_json': _json(status_labels),
        'call_status_data_json': _json(call_status_data),
        'call_status_labels_json': _json(call_status_labels),

        'emp_chart_names_json': _json(emp_chart_names),
        'emp_chart_values_json': _json(emp_chart_values),

        # ═══ داده‌های معمولی (برای json_script) ═══
        'compare_data': compare_data,
        'funnel': funnel_data,
        'top_products': top_products_list,
        'employee_perf': employee_perf_list,
    }


# ═══════════════════════════════════════════
# Views
# ═══════════════════════════════════════════

@login_required
@require_permission('dashboard.view')
def home(request):
    """داشبورد اصلی با فیلتر تاریخ"""
    from_date_str = request.GET.get('from_date', '').strip()
    to_date_str = request.GET.get('to_date', '').strip()

    from_date = _parse_jalali_date(from_date_str) if from_date_str else None
    to_date = _parse_jalali_date(to_date_str) if to_date_str else None

    context = _get_dashboard_data(from_date, to_date)
    context['from_date_jalali'] = from_date_str
    context['to_date_jalali'] = to_date_str

    return render(request, 'dashboard/home.html', context)


@login_required
def global_search(request):
    """جستجوی سراسری — برای همه‌ی کاربران لاگین‌شده"""
    query = request.GET.get('q', '').strip()
    results = {'customers': [], 'calls': [], 'products': [], 'total': 0}

    if query and len(query) >= 2:
        results['customers'] = list(Customer.objects.filter(
            Q(name__icontains=query) | Q(mobile__icontains=query) |
            Q(email__icontains=query) | Q(national_id__icontains=query)
        )[:10])
        results['calls'] = list(Call.objects.filter(
            Q(caller_name__icontains=query) | Q(call_number__icontains=query) |
            Q(notes__icontains=query)
        )[:10])
        results['products'] = list(Product.objects.filter(
            Q(name__icontains=query) | Q(code__icontains=query) |
            Q(description__icontains=query)
        )[:10])
        results['total'] = (len(results['customers']) + len(results['calls'])
                            + len(results['products']))

    return render(request, 'dashboard/search.html', {
        'query': query, 'results': results,
    })


@login_required
@require_permission('dashboard.export')
def export_excel(request):
    """خروجی Excel از تمام گزارشات"""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    except ImportError:
        return HttpResponse(
            'openpyxl نصب نیست. لطفاً pip install openpyxl را اجرا کنید.',
            status=500
        )

    from_date_str = request.GET.get('from_date', '').strip()
    to_date_str = request.GET.get('to_date', '').strip()

    from_date = _parse_jalali_date(from_date_str) if from_date_str else None
    to_date = _parse_jalali_date(to_date_str) if to_date_str else None

    data = _get_dashboard_data(from_date, to_date)

    wb = Workbook()

    # ═══ استایل‌ها ═══
    header_font = Font(bold=True, color='FFFFFF', size=12)
    header_fill = PatternFill('solid', fgColor='2E86AB')
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin'),
    )

    # ═══ Sheet 1: خلاصه (KPI) ═══
    ws = wb.active
    ws.title = 'خلاصه'
    ws.sheet_view.rightToLeft = True

    ws.append(['گزارش CRM دیجیران'])
    ws.merge_cells('A1:C1')
    ws['A1'].font = Font(bold=True, size=16, color='2E86AB')
    ws['A1'].alignment = center
    ws.row_dimensions[1].height = 30

    ws.append([])
    ws.append([f"تاریخ گزارش: {data['today']}"])
    ws.append([])

    ws.append(['شاخص', 'مقدار', 'واحد'])
    for cell in ws[ws.max_row]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border

    kpis = data['kpis']
    kpi_rows = [
        ('کل مشتریان', kpis['total_customers'], 'نفر'),
        ('مشتریان فعال', kpis['active_customers'], 'نفر'),
        ('مشتریان بالقوه (لید)', kpis['lead_customers'], 'نفر'),
        ('کل تماس‌ها', kpis['total_calls'], 'تماس'),
        ('تماس‌های این ماه', kpis['calls_this_month'], 'تماس'),
        ('کل فاکتورها', kpis['total_invoices'], 'فاکتور'),
        ('مجموع فروش', int(kpis['total_sales']), 'تومان'),
        ('فروش این ماه', int(kpis['sales_this_month']), 'تومان'),
        ('فروش ماه قبل', int(kpis['sales_last_month']), 'تومان'),
        ('تغییر ماهانه', f"{kpis['sales_change']}٪", '—'),
        ('فروش سال قبل (همین ماه)', int(kpis['sales_last_year']), 'تومان'),
        ('تغییر سالانه', f"{kpis['yearly_change']}٪", '—'),
        ('وظایف باز', kpis['open_tasks'], 'وظیفه'),
        ('وظایف عقب‌افتاده', kpis['overdue_tasks'], 'وظیفه'),
        ('مرخصی‌های در انتظار', kpis['pending_leaves'], 'درخواست'),
    ]

    for row in kpi_rows:
        ws.append(row)
        for cell in ws[ws.max_row]:
            cell.alignment = center
            cell.border = border

    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 20
    ws.column_dimensions['C'].width = 15

    # ═══ Sheet 2: فروش ماهانه ═══
    ws2 = wb.create_sheet('فروش ماهانه')
    ws2.sheet_view.rightToLeft = True

    ws2.append(['ماه', 'فروش (تومان)'])
    for cell in ws2[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border

    for label, value in zip(data['sales_labels'], data['sales_data']):
        ws2.append([label, int(value)])
        for cell in ws2[ws2.max_row]:
            cell.alignment = center
            cell.border = border

    ws2.column_dimensions['A'].width = 20
    ws2.column_dimensions['B'].width = 25

    # ═══ Sheet 3: عملکرد کارمندان ═══
    ws3 = wb.create_sheet('عملکرد کارمندان')
    ws3.sheet_view.rightToLeft = True

    ws3.append(['کارمند', 'تعداد فاکتور', 'مجموع فروش (تومان)'])
    for cell in ws3[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border

    for emp in data['employee_perf']:
        ws3.append([emp['name'], emp['invoice_count'], int(emp['total_sales'])])
        for cell in ws3[ws3.max_row]:
            cell.alignment = center
            cell.border = border

    ws3.column_dimensions['A'].width = 25
    ws3.column_dimensions['B'].width = 15
    ws3.column_dimensions['C'].width = 25

    # ═══ Sheet 4: پرفروش‌ترین کالاها ═══
    ws4 = wb.create_sheet('پرفروش‌ترین کالاها')
    ws4.sheet_view.rightToLeft = True

    ws4.append(['کالا', 'تعداد فروش', 'درآمد (تومان)'])
    for cell in ws4[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border

    for p in data['top_products']:
        ws4.append([p['name'], p['qty'], int(p['revenue'])])
        for cell in ws4[ws4.max_row]:
            cell.alignment = center
            cell.border = border

    ws4.column_dimensions['A'].width = 30
    ws4.column_dimensions['B'].width = 15
    ws4.column_dimensions['C'].width = 25

    # ═══ Sheet 5: توزیع منابع جذب ═══
    ws5 = wb.create_sheet('منابع جذب')
    ws5.sheet_view.rightToLeft = True

    ws5.append(['منبع', 'تعداد مشتری'])
    for cell in ws5[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border

    for label, value in zip(data['source_labels'], data['source_data']):
        ws5.append([label, value])
        for cell in ws5[ws5.max_row]:
            cell.alignment = center
            cell.border = border

    ws5.column_dimensions['A'].width = 25
    ws5.column_dimensions['B'].width = 15

    # ═══ ارسال فایل ═══
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f'crm-report-{datetime.now().strftime("%Y%m%d-%H%M")}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response