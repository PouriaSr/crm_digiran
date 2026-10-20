#!/usr/bin/env python3
"""
Major Upgrade: Customer Hub with 5 Tabs (Info, Call, Followup, Visit, Invoice).
Applies DB changes, new views, new UI, and updates RBAC.
"""
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
BACKUP_DIR = BASE / f'.upgrade_hub_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'

def backup_file(path):
    if not path.exists(): return
    rel = path.relative_to(BASE)
    dest = BACKUP_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)

def patch_file(rel_path, replacements):
    p = BASE / rel_path
    if not p.exists(): return
    backup_file(p)
    content = p.read_text(encoding='utf-8')
    for old, new in replacements:
        if new not in content:
            content = content.replace(old, new)
    p.write_text(content, encoding='utf-8')
    print(f"  OK Patched: {rel_path}")

def write_file(rel_path, content):
    p = BASE / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists(): backup_file(p)
    p.write_text(content.lstrip("\n"), encoding='utf-8')
    print(f"  OK Created/Updated: {rel_path}")

# ═══════════════════════════════════════════════════════════
# 1. Database Models
# ═══════════════════════════════════════════════════════════
def update_models():
    # -- Customer Model --
    patch_file('customers/models.py', [(
        "class Customer(models.Model):",
        """class Customer(models.Model):
    CUSTOMER_TYPE_CHOICES = [
        ('none', 'فاقد شرایط'),
        ('cash', 'نقدی'),
        ('cheque', 'چک'),
        ('installment', 'قسطی'),
    ]
    is_lead = models.BooleanField('سرنخ', default=False)
    customer_type = models.CharField('نوع مشتری', max_length=20, choices=CUSTOMER_TYPE_CHOICES, default='none')
    cheques_count = models.PositiveSmallIntegerField('تعداد چک', null=True, blank=True)
    installments_count = models.PositiveSmallIntegerField('تعداد اقساط', null=True, blank=True)
"""
    )])
    
    # -- Visit Model --
    with open(BASE / 'customers/models.py', 'a', encoding='utf-8') as f:
        f.write("""

class Visit(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='visits', verbose_name='مشتری')
    visit_date = models.DateTimeField('تاریخ مراجعه', default=timezone.now)
    is_successful = models.BooleanField('مراحل با موفقیت طی شد؟', default=False)
    notes = models.TextField('یادداشت', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='ثبت‌کننده')
    created_at = models.DateTimeField('تاریخ ثبت', auto_now_add=True)

    class Meta:
        verbose_name = 'مراجعه حضوری'
        verbose_name_plural = 'مراجعات حضوری'
        ordering = ['-visit_date']

    def __str__(self):
        return f"{self.customer.name} - {self.visit_date.strftime('%Y/%m/%d')}"
""")
    print("  OK Updated customers/models.py")

# ═══════════════════════════════════════════════════════════
# 2. Forms
# ═══════════════════════════════════════════════════════════
def update_forms():
    with open(BASE / 'customers/forms.py', 'a', encoding='utf-8') as f:
        f.write("""

class HubCallForm(forms.Form):
    mobile = forms.CharField(label='شماره تماس', max_length=15, required=True,
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg', 'dir': 'ltr', 'placeholder': '09123456789', 'id': 'hub_call_mobile'}))
    name = forms.CharField(label='نام و نام خانوادگی', max_length=200, required=False,
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg', 'id': 'hub_call_name'}))
    call_type = forms.ChoiceField(label='نوع تماس', choices=[('incoming', 'ورودی (چت دیوار / تماس مشتری / از دست رفته)'), ('outgoing', 'خروجی')],
        widget=forms.Select(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg'}))
    source = forms.ModelChoiceField(label='منبع', queryset=__import__('ads.models', fromlist=['AdSource']).AdSource.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg'}))
    customer_type = forms.ChoiceField(label='نوع مشتری', choices=__import__('customers.models', fromlist=['Customer']).Customer.CUSTOMER_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg', 'id': 'hub_customer_type'}))
    installments_count = forms.IntegerField(label='تعداد اقساط', required=False, min_value=1,
        widget=forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg', 'id': 'hub_installments'}))
    cheques_count = forms.IntegerField(label='تعداد چک', required=False, min_value=1, max_value=5,
        widget=forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg', 'id': 'hub_cheques'}))
    notes = forms.CharField(label='توضیحات (الزامی)', required=True,
        widget=forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg', 'rows': 3, 'placeholder': 'شرح مکالمه...'}))
    status = forms.ChoiceField(label='وضعیت مشتری', choices=[('lead', 'بالقوه (نیازمند پیگیری)'), ('active', 'بالفعل (سرنخ)')],
        widget=forms.Select(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg', 'id': 'hub_status'}))
    follow_up_date = forms.CharField(label='تاریخ پیگیری', required=False,
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg', 'data-jdp': '', 'id': 'hub_followup', 'placeholder': '1405/01/01'}))

class HubVisitForm(forms.Form):
    customer = forms.ModelChoiceField(label='مشتری', queryset=__import__('customers.models', fromlist=['Customer']).Customer.objects.all(),
        widget=forms.Select(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg'}))
    is_successful = forms.BooleanField(label='مراحل با موفقیت طی شد؟ (انتقال به پرونده)', required=False,
        widget=forms.CheckboxInput(attrs={'class': 'w-5 h-5 text-blue-600 rounded'}))
    notes = forms.CharField(label='یادداشت مراجعه', required=True,
        widget=forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border rounded-lg', 'rows': 3}))
""")
    print("  OK Updated customers/forms.py")

# ═══════════════════════════════════════════════════════════
# 3. Views & URLs
# ═══════════════════════════════════════════════════════════
def update_views():
    with open(BASE / 'customers/hub_views.py', 'w', encoding='utf-8') as f:
        f.write("""from django.shortcuts import render, redirect, get_object_or_404
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
    
    context = {
        'active_tab': tab,
        'customers': customers[:50],
        'followups': followups,
        'invoices': Invoice.objects.all().order_by('-created_at')[:20],
        'call_form': HubCallForm(),
        'visit_form': HubVisitForm(),
    }
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
            
            if form.cleaned_data['status'] == 'active':
                customer.is_lead = True
                customer.status = 'active'
                follow_up = None
            else:
                customer.status = 'lead'
                follow_up = form.cleaned_data['follow_up_date']
                
            customer.save()
            
            # Create Call Record
            Call.objects.create(
                customer=customer,
                caller_name=customer.name,
                call_number=mobile,
                call_type=form.cleaned_data['call_type'],
                purpose='sale',
                status='answered',
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
            if visit.is_successful:
                messages.success(request, 'مراجعه ثبت شد. انتقال به پرونده...')
                return redirect('customers:hub') # Replace with actual file page later
            messages.success(request, 'مراجعه ثبت شد.')
            return redirect(f"{request.path_info}?tab=visit")
    return redirect('customers:hub')
""")

    patch_file('customers/urls.py', [(
        "path('', views.customer_list, name='list'),",
        "path('', views.customer_list, name='list'),\n    path('hub/', __import__('customers.hub_views', fromlist=['customer_hub']).customer_hub, name='hub'),\n    path('hub/call/', __import__('customers.hub_views', fromlist=['hub_submit_call']).hub_submit_call, name='hub_submit_call'),\n    path('hub/visit/', __import__('customers.hub_views', fromlist=['hub_submit_visit']).hub_submit_visit, name='hub_submit_visit'),"
    )])

# ═══════════════════════════════════════════════════════════
# 4. RBAC Permissions
# ═══════════════════════════════════════════════════════════
def update_rbac():
    patch_file('accounts/permissions.py', [(
        "'customers.delete': [ROLE_ADMIN, ROLE_SALES_MANAGER],",
        "'customers.delete': [ROLE_ADMIN, ROLE_SALES_MANAGER],\n    'customers.visit': [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT, ROLE_OPERATOR],\n    'customers.followup': [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES, ROLE_SUPPORT],"
    )])

# ═══════════════════════════════════════════════════════════
# 5. The UI Template (Massive File)
# ═══════════════════════════════════════════════════════════
def create_hub_template():
    html = """{% extends 'base.html' %}
{% load fa_numbers %}

{% block title %}مرکز مشتریان{% endblock %}
{% block mobile_title %}مرکز مشتریان{% endblock %}

{% block content %}
<div x-data="{ tab: '{{ active_tab }}' }" class="max-w-7xl mx-auto">
    
    <!-- TABS HEADER -->
    <div class="bg-white rounded-xl shadow-sm mb-6 overflow-x-auto sticky top-14 lg:top-0 z-20">
        <div class="flex min-w-max border-b border-gray-100">
            <button @click="tab = 'info'" :class="tab === 'info' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'" class="flex-1 py-4 px-6 text-center border-b-2 font-medium text-sm transition">
                <span class="text-lg mb-1 block">👥</span> اطلاعات
            </button>
            <button @click="tab = 'call'" :class="tab === 'call' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'" class="flex-1 py-4 px-6 text-center border-b-2 font-medium text-sm transition">
                <span class="text-lg mb-1 block">📞</span> تماس جدید
            </button>
            <button @click="tab = 'followup'" :class="tab === 'followup' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'" class="flex-1 py-4 px-6 text-center border-b-2 font-medium text-sm transition relative">
                <span class="text-lg mb-1 block">⏰</span> پیگیری
                {% if followups.count > 0 %}<span class="absolute top-2 right-2 bg-red-500 text-white text-[10px] px-2 py-0.5 rounded-full">{{ followups.count }}</span>{% endif %}
            </button>
            <button @click="tab = 'visit'" :class="tab === 'visit' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'" class="flex-1 py-4 px-6 text-center border-b-2 font-medium text-sm transition">
                <span class="text-lg mb-1 block">🏢</span> مراجعه حضوری
            </button>
            <button @click="tab = 'invoice'" :class="tab === 'invoice' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'" class="flex-1 py-4 px-6 text-center border-b-2 font-medium text-sm transition">
                <span class="text-lg mb-1 block">📄</span> فاکتورها
            </button>
        </div>
    </div>

    <!-- TAB 1: INFO -->
    <div x-show="tab === 'info'" x-transition.opacity class="space-y-6">
        <div class="flex flex-col md:flex-row justify-between gap-4">
            <form method="get" class="flex-1 flex gap-2">
                <input type="hidden" name="tab" value="info">
                <input type="text" name="q" value="{{ request.GET.q }}" placeholder="جستجوی مشتری..." class="w-full px-4 py-2 border rounded-lg">
                <button type="submit" class="px-6 py-2 bg-blue-600 text-white rounded-lg">جستجو</button>
            </form>
            {% if 'customers.add' in user_permissions %}
            <a href="{% url 'customers:create' %}" class="px-6 py-2 bg-green-600 text-white rounded-lg text-center flex items-center justify-center gap-2">
                + مشتری جدید
            </a>
            {% endif %}
        </div>
        
        <div class="bg-white rounded-xl shadow-sm overflow-hidden">
            <table class="responsive-table w-full text-sm">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="p-4 text-right">نام / شرکت</th>
                        <th class="p-4 text-right">موبایل</th>
                        <th class="p-4 text-right">وضعیت</th>
                        <th class="p-4 text-right">نوع</th>
                        <th class="p-4 text-right">سرنخ</th>
                        <th class="p-4 text-right">عملیات</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                    {% for c in customers %}
                    <tr class="hover:bg-gray-50">
                        <td class="p-4 text-right font-medium" data-label="نام">{{ c.name }}</td>
                        <td class="p-4 text-right font-mono" data-label="موبایل" dir="ltr">{{ c.mobile }}</td>
                        <td class="p-4 text-right" data-label="وضعیت">{{ c.get_status_display }}</td>
                        <td class="p-4 text-right" data-label="نوع">{{ c.get_customer_type_display }}</td>
                        <td class="p-4 text-right" data-label="سرنخ">{% if c.is_lead %}<span class="bg-purple-100 text-purple-700 px-2 py-1 rounded text-xs">سرنخ</span>{% else %}-{% endif %}</td>
                        <td class="p-4 text-right">
                            <a href="{% url 'customers:detail' c.pk %}" class="text-blue-600">جزئیات</a>
                        </td>
                    </tr>
                    {% empty %}
                    <tr><td colspan="6" class="p-8 text-center text-gray-400">مشتری یافت نشد</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- TAB 2: CALL -->
    <div x-show="tab === 'call'" x-transition.opacity style="display: none;">
        <div class="bg-white rounded-xl shadow-sm p-6 max-w-3xl mx-auto">
            <h2 class="text-xl font-bold mb-6">ثبت تماس جدید</h2>
            <form method="post" action="{% url 'customers:hub_submit_call' %}" class="space-y-4">
                {% csrf_token %}
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">شماره تماس *</label>
                        {{ call_form.mobile }}
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">نام و نام خانوادگی</label>
                        {{ call_form.name }}
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">نوع تماس</label>
                        {{ call_form.call_type }}
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">منبع</label>
                        {{ call_form.source }}
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">نوع مشتری</label>
                        {{ call_form.customer_type }}
                    </div>
                    <div x-show="true">
                        <label class="block text-sm font-medium text-gray-700 mb-1">تعداد اقساط</label>
                        {{ call_form.installments_count }}
                    </div>
                    <div x-show="true">
                        <label class="block text-sm font-medium text-gray-700 mb-1">تعداد چک</label>
                        {{ call_form.cheques_count }}
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">وضعیت مشتری</label>
                        {{ call_form.status }}
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">تاریخ پیگیری (اگر بالقوه)</label>
                        {{ call_form.follow_up_date }}
                    </div>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">توضیحات (الزامی) *</label>
                    {{ call_form.notes }}
                </div>
                <button type="submit" class="w-full py-3 bg-blue-600 text-white rounded-lg font-bold">ثبت تماس</button>
            </form>
        </div>
    </div>

    <!-- TAB 3: FOLLOWUP -->
    <div x-show="tab === 'followup'" x-transition.opacity style="display: none;">
        <div class="bg-white rounded-xl shadow-sm overflow-hidden">
            <div class="p-4 border-b border-gray-100 bg-orange-50 text-orange-800 text-sm">
                مشتریانی که نیاز به پیگیری دارند (بالقوه)
            </div>
            <table class="responsive-table w-full text-sm">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="p-4 text-right">مشتری</th>
                        <th class="p-4 text-right">موبایل</th>
                        <th class="p-4 text-right">تاریخ پیگیری</th>
                        <th class="p-4 text-right">یادداشت قبلی</th>
                        <th class="p-4 text-right">عملیات</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                    {% for f in followups %}
                    <tr class="hover:bg-gray-50">
                        <td class="p-4 text-right font-medium" data-label="مشتری">{{ f.customer.name }}</td>
                        <td class="p-4 text-right font-mono" data-label="موبایل" dir="ltr">{{ f.customer.mobile }}</td>
                        <td class="p-4 text-right text-red-600 font-bold" data-label="تاریخ">{{ f.follow_up_date|jdate:"Y/m/d" }}</td>
                        <td class="p-4 text-right text-xs text-gray-500" data-label="یادداشت">{{ f.notes|truncatechars:30 }}</td>
                        <td class="p-4 text-right">
                            <a href="{% url 'calls:edit' f.pk %}" class="px-3 py-1 bg-blue-100 text-blue-700 rounded text-xs">ثبت نتیجه</a>
                        </td>
                    </tr>
                    {% empty %}
                    <tr><td colspan="5" class="p-8 text-center text-gray-400">هیچ پیگیری در انتظاری وجود ندارد.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- TAB 4: VISIT -->
    <div x-show="tab === 'visit'" x-transition.opacity style="display: none;">
        <div class="bg-white rounded-xl shadow-sm p-6 max-w-3xl mx-auto">
            <h2 class="text-xl font-bold mb-6">ثبت مراجعه حضوری</h2>
            <form method="post" action="{% url 'customers:hub_submit_visit' %}" class="space-y-4">
                {% csrf_token %}
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">انتخاب مشتری</label>
                    {{ visit_form.customer }}
                </div>
                <div class="bg-blue-50 p-4 rounded-lg flex items-center gap-3">
                    {{ visit_form.is_successful }}
                    <label class="text-sm font-medium text-blue-800 cursor-pointer">مراحل با موفقیت طی شد؟ (انتقال به پرونده)</label>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">یادداشت مراجعه *</label>
                    {{ visit_form.notes }}
                </div>
                <button type="submit" class="w-full py-3 bg-green-600 text-white rounded-lg font-bold">ثبت مراجعه</button>
            </form>
        </div>
    </div>

    <!-- TAB 5: INVOICE -->
    <div x-show="tab === 'invoice'" x-transition.opacity style="display: none;">
        <div class="flex justify-between items-center mb-4">
            <h2 class="text-lg font-bold">آخرین فاکتورها</h2>
            <a href="{% url 'sales:create' %}" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">+ فاکتور جدید</a>
        </div>
        <div class="bg-white rounded-xl shadow-sm overflow-hidden">
            <table class="responsive-table w-full text-sm">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="p-4 text-right">شماره</th>
                        <th class="p-4 text-right">مشتری</th>
                        <th class="p-4 text-right">مبلغ</th>
                        <th class="p-4 text-right">وضعیت</th>
                        <th class="p-4 text-right">تاریخ</th>
                        <th class="p-4 text-right">عملیات</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                    {% for inv in invoices %}
                    <tr class="hover:bg-gray-50">
                        <td class="p-4 text-right font-mono text-xs" data-label="شماره">{{ inv.number }}</td>
                        <td class="p-4 text-right" data-label="مشتری">{{ inv.customer.name }}</td>
                        <td class="p-4 text-right font-bold" data-label="مبلغ">{{ inv.total|floatformat:0 }}</td>
                        <td class="p-4 text-right" data-label="وضعیت">{{ inv.get_status_display }}</td>
                        <td class="p-4 text-right text-xs text-gray-500" data-label="تاریخ">{{ inv.issue_date|jdate:"Y/m/d" }}</td>
                        <td class="p-4 text-right">
                            <a href="{% url 'sales:detail' inv.pk %}" class="text-blue-600">مشاهده</a>
                        </td>
                    </tr>
                    {% empty %}
                    <tr><td colspan="6" class="p-8 text-center text-gray-400">فاکتوری یافت نشد</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

</div>

<!-- Script for dynamic form fields -->
<script>
document.addEventListener('DOMContentLoaded', function() {
    const typeSelect = document.getElementById('hub_customer_type');
    const installDiv = document.getElementById('hub_installments').closest('div');
    const chequeDiv = document.getElementById('hub_cheques').closest('div');

    function toggleFields() {
        const val = typeSelect.value;
        installDiv.style.display = (val === 'installment') ? 'block' : 'none';
        chequeDiv.style.display = (val === 'cheque') ? 'block' : 'none';
    }
    
    if (typeSelect) {
        typeSelect.addEventListener('change', toggleFields);
        toggleFields();
    }
});
</script>
{% endblock %}
"""
    write_file('templates/customers/hub.html', html)

# ═══════════════════════════════════════════════════════════
# 6. Execute
# ═══════════════════════════════════════════════════════════
def main():
    print("Starting major upgrade for Customer Hub...\n")
    update_models()
    update_forms()
    update_views()
    update_rbac()
    create_hub_template()
    
    print("\nRunning migrations...")
    subprocess.run([sys.executable, 'manage.py', 'makemigrations', 'customers'], check=True)
    subprocess.run([sys.executable, 'manage.py', 'migrate'], check=True)
    print("\n🎉 Success! Please restart your server and navigate to /customers/hub/")

if __name__ == '__main__':
    main()
