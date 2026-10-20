from django.contrib.auth.models import User
import jdatetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from accounts.permissions import require_permission
from .models import Customer, Visit
from .forms import HubCallForm, HubVisitForm
from calls.models import Call
from sales.models import Invoice

@login_required
@require_permission('customers.view')
def customer_hub(request):
    tab = request.GET.get('tab', 'info')
    
    customers = Customer.objects.all().order_by('-created_at')
    search = request.GET.get('q', '').strip()
    if search:
        customers = customers.filter(Q(name__icontains=search) | Q(mobile__icontains=search))
    
    followups = Call.objects.filter(is_followed_up=False, follow_up_date__isnull=False).order_by('follow_up_date')
    
    from django.db.models import Sum
    from datetime import date
    
    total_customers = Customer.objects.count()
    total_leads = Customer.objects.filter(status='lead').count()
    pending_followups = followups.count()
    total_invoices = Invoice.objects.count()
    recent_revenue = Invoice.objects.filter(status='paid').aggregate(total=Sum('total'))['total'] or 0

    context = {
        'active_tab': tab,
        'stats': {
            'total_customers': total_customers,
            'total_leads': total_leads,
            'pending_followups': pending_followups,
            'total_invoices': total_invoices,
            'recent_revenue': recent_revenue,
        },
        'customers': customers[:50],
        'followups': followups,
        'invoices': Invoice.objects.all().order_by('-created_at')[:20],
        'reassign_users': User.objects.filter(
            is_active=True, is_staff=True,
        ).order_by('first_name', 'last_name', 'username'),
        'call_form': HubCallForm(),
        'visit_form': HubVisitForm(),
    }
    
    # ═══ AJAX Live Search Support ═══
    if request.headers.get('HX-Request') and tab == 'info':
        return render(request, 'customers/hub_table_partial.html', context)
    return render(request, 'customers/hub.html', context)

@login_required
@require_permission('customers.add')
def hub_submit_call(request):
    if request.method == 'POST':
        form = HubCallForm(request.POST)
        if form.is_valid():
            mobile = form.cleaned_data['mobile']
            customer = Customer.objects.filter(mobile=mobile).first()
            is_new = False
            
            if not customer:
                is_new = True
                customer = Customer.objects.create(
                    mobile=mobile, 
                    name=form.cleaned_data['name'] or 'ناشناس',
                    status='lead',
                    created_by=request.user
                )
            
            # Update customer details based on call
            customer.customer_type = form.cleaned_data['customer_type']
            customer.installments_count = form.cleaned_data['installments_count']
            customer.cheques_count = form.cleaned_data['cheques_count']

            # ⭐ Save AdSource (fix v12)
            ad_source = form.cleaned_data.get('source')
            if ad_source:
                customer.ad_source = ad_source
            
            if form.cleaned_data['status'] == 'active':
                customer.status = 'active'
                follow_up = None
            else:
                customer.status = 'lead'
                follow_up = form.cleaned_data['follow_up_date']
                
            customer.save()
            
            # Map custom call types to Call model
            custom_type = form.cleaned_data['call_type']
            if custom_type == 'outgoing':
                c_type, c_status = 'outgoing', 'answered'
            elif custom_type == 'incoming_missed':
                c_type, c_status = 'incoming', 'missed'
            else:
                c_type, c_status = 'incoming', 'answered'

            # Convert Jalali date to Gregorian
            follow_up = None
            if form.cleaned_data['status'] == 'lead':
                raw_date = form.cleaned_data['follow_up_date']
                if raw_date:
                    try:
                        raw_date = str(raw_date).replace('-', '/')
                        y, m, d = map(int, raw_date.split('/'))
                        follow_up = jdatetime.date(y, m, d).togregorian()
                    except Exception:
                        pass

            # Create Call Record
            Call.objects.create(
                customer=customer,
                caller_name=customer.name,
                call_number=mobile,
                call_type=c_type,
                purpose='sale',
                status=c_status,
                notes=form.cleaned_data['notes'],
                called_by=request.user,
                created_by=request.user,
                follow_up_date=follow_up
            )
            messages.success(request, 'تماس با موفقیت ثبت شد.')
            return redirect(f"{request.path_info}?tab=followup" if follow_up else f"{request.path_info}?tab=info")
    messages.error(request, 'خطا در ثبت تماس.')
    return redirect('customers:hub')

@login_required
@require_permission('customers.add')
def hub_submit_visit(request):
    if request.method == 'POST':
        form = HubVisitForm(request.POST)
        if form.is_valid():
            visit = form.save(commit=False)
            visit.created_by = request.user
            visit.save()
            visit.customer.status = 'active'
            visit.customer.save()
            if visit.is_successful:
                messages.success(request, 'مراجعه ثبت شد. انتقال به پرونده...')
                return redirect('customers:hub') # Replace with actual file page later
            messages.success(request, 'مراجعه ثبت شد.')
            return redirect(f"{request.path_info}?tab=visit")
    return redirect('customers:hub')


from django.http import JsonResponse
from django.views.decorators.http import require_GET

@login_required
@require_GET
def hub_check_customer(request):
    mobile = request.GET.get('mobile', '').strip()
    if len(mobile) < 10:
        return JsonResponse({'exists': False})
    customer = Customer.objects.filter(mobile=mobile).first()
    if customer:
        return JsonResponse({
            'exists': True,
            'name': customer.name,
            'type': customer.get_customer_type_display(),
            'status': customer.get_status_display()
        })
    return JsonResponse({'exists': False})


# ═══════════════════════════════════════════════════════════
# ارجاع مشتری به کارمند دیگر (Customer Reassign)
# ═══════════════════════════════════════════════════════════
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404


@login_required
@require_permission('customers.edit')
@require_POST
def customer_reassign(request, pk):
    """ارجاع مشتری به کارمند دیگر — پشتیبانی از AJAX"""
    customer = get_object_or_404(Customer, pk=pk)
    new_user_id = request.POST.get('assigned_to')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not new_user_id:
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'کارمند جدید انتخاب نشده'}, status=400)
        messages.error(request, 'لطفاً یک کارمند انتخاب کنید.')
        return redirect('customers:detail', pk=customer.pk)

    try:
        new_user = User.objects.get(pk=new_user_id, is_active=True)
    except User.DoesNotExist:
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'کارمند یافت نشد'}, status=404)
        messages.error(request, 'کارمند انتخابی یافت نشد.')
        return redirect('customers:detail', pk=customer.pk)

    old_user = customer.assigned_to
    customer.assigned_to = new_user
    customer.save(update_fields=['assigned_to', 'updated_at'])

    old_name = '—'
    if old_user:
        old_name = old_user.get_full_name() or old_user.username
    new_name = new_user.get_full_name() or new_user.username

    if is_ajax:
        return JsonResponse({
            'success': True,
            'new_user_name': new_name,
            'old_user_name': old_name,
            'message': f'مشتری از «{old_name}» به «{new_name}» ارجاع شد.'
        })

    messages.success(request, f'مشتری از «{old_name}» به «{new_name}» ارجاع شد.')
    return redirect('customers:detail', pk=customer.pk)
