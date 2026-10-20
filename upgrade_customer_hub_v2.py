#!/usr/bin/env python3
"""
Major Upgrade V2: Premium Customer Hub (5 Tabs) + Route Merging & UI/UX Polish.
"""
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
BACKUP_DIR = BASE / f'.hub_v2_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'

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
# 1. API for Real-time Phone Check
# ═══════════════════════════════════════════════════════════
def create_api():
    with open(BASE / 'customers/hub_views.py', 'a', encoding='utf-8') as f:
        f.write("""

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
""")

# ═══════════════════════════════════════════════════════════
# 2. Merge Routes (Redirect old pages to new Hub)
# ═══════════════════════════════════════════════════════════
def merge_routes():
    # Redirect Customers App
    write_file('customers/urls_override.py', """
from django.urls import path
from django.shortcuts import redirect
from . import views, hub_views

app_name = 'customers'
def to_hub(request): return redirect('/customers/hub/?tab=info')
def to_call(request): return redirect('/customers/hub/?tab=call')
def to_visit(request): return redirect('/customers/hub/?tab=visit')

urlpatterns = [
    path('', to_hub),
    path('hub/', hub_views.customer_hub, name='hub'),
    path('hub/call/', hub_views.hub_submit_call, name='hub_submit_call'),
    path('hub/visit/', hub_views.hub_submit_visit, name='hub_submit_visit'),
    path('hub/api/check/', hub_views.hub_check_customer, name='hub_check_api'),
    # Keep detail/create/edit intact
    path('new/', views.customer_create, name='create'),
    path('<int:pk>/', views.customer_detail, name='detail'),
    path('<int:pk>/edit/', views.customer_edit, name='edit'),
]
    """)
    patch_file('customers/urls.py', [("urlpatterns = [", "from .urls_override import urlpatterns\n_urlpatterns_ignored = [")])

    # Redirect Calls App
    write_file('calls/urls.py', """
from django.urls import path
from django.shortcuts import redirect
from . import views
app_name = 'calls'
def to_hub(request): return redirect('/customers/hub/?tab=followup')

urlpatterns = [
    path('', to_hub),
    path('new/', views.call_create, name='create'),
    path('<int:pk>/', views.call_detail, name='detail'),
    path('<int:pk>/edit/', views.call_edit, name='edit'),
]
    """)

    # Redirect Sales/Invoices App
    write_file('sales/urls.py', """
from django.urls import path
from django.shortcuts import redirect
from . import views
app_name = 'sales'
def to_hub(request): return redirect('/customers/hub/?tab=invoice')

urlpatterns = [
    path('', to_hub),
    path('new/', views.invoice_create, name='create'),
    path('<int:pk>/', views.invoice_detail, name='detail'),
    path('<int:pk>/print/', views.invoice_print, name='print'),
]
    """)

# ═══════════════════════════════════════════════════════════
# 3. Update Base.html Sidebar & Bottom Nav
# ═══════════════════════════════════════════════════════════
def update_base_html():
    patch_file('templates/base.html', [
        ("{% url 'customers:list' %}", "{% url 'customers:hub' %}"),
        ("{% url 'calls:list' %}", "{% url 'customers:hub' %}?tab=followup"),
        ("{% url 'sales:list' %}", "{% url 'customers:hub' %}?tab=invoice"),
        ("مشتریان و مخاطبین", "مرکز مشتریان"),
        ("مشتریان", "مرکز مشتریان"),
        ("تماس‌ها", "پیگیری‌ها"),
        ("فاکتورها", "فاکتورها"),
        # Update active states roughly
        ("request.resolver_match.app_name == 'customers'", "request.resolver_match.app_name == 'customers'"),
    ])

# ═══════════════════════════════════════════════════════════
# 4. Stunning UI (hub.html)
# ═══════════════════════════════════════════════════════════
def create_hub_template():
    html = """{% extends 'base.html' %}
{% load fa_numbers %}

{% block title %}مرکز مشتریان{% endblock %}
{% block mobile_title %}مرکز مشتریان{% endblock %}

{% block content %}
<div x-data="{ 
        tab: new URLSearchParams(window.location.search).get('tab') || 'info',
        customerType: 'none',
        customerStatus: 'lead',
        mobile: '',
        existingCustomer: null,
        checking: false,
        checkMobile() {
            if(this.mobile.length >= 10) {
                this.checking = true;
                fetch('{% url \"customers:hub_check_api\" %}?mobile=' + this.mobile)
                    .then(r => r.json())
                    .then(data => {
                        this.existingCustomer = data.exists ? data : null;
                        this.checking = false;
                        if(data.exists) {
                            document.getElementById('hub_call_name').value = data.name;
                        }
                    });
            } else {
                this.existingCustomer = null;
            }
        }
     }" class="max-w-7xl mx-auto pb-10">
    
    <!-- Header & Tabs -->
    <div class="bg-white rounded-2xl shadow-sm mb-6 overflow-hidden">
        <div class="flex overflow-x-auto hide-scrollbar border-b border-gray-100 bg-gray-50/50">
            <button @click="tab = 'info'; window.history.replaceState(null, '', '?tab=info')" :class="tab === 'info' ? 'border-blue-600 text-blue-600 bg-white' : 'border-transparent text-gray-500 hover:text-gray-800 hover:bg-gray-50'" class="flex-shrink-0 w-32 md:w-auto md:flex-1 py-4 px-4 text-center border-b-2 font-medium text-sm transition-all duration-200">
                <span class="text-xl block mb-1 opacity-80">👥</span> اطلاعات
            </button>
            <button @click="tab = 'call'; window.history.replaceState(null, '', '?tab=call')" :class="tab === 'call' ? 'border-blue-600 text-blue-600 bg-white' : 'border-transparent text-gray-500 hover:text-gray-800 hover:bg-gray-50'" class="flex-shrink-0 w-32 md:w-auto md:flex-1 py-4 px-4 text-center border-b-2 font-medium text-sm transition-all duration-200">
                <span class="text-xl block mb-1 opacity-80">📞</span> تماس جدید
            </button>
            <button @click="tab = 'followup'; window.history.replaceState(null, '', '?tab=followup')" :class="tab === 'followup' ? 'border-blue-600 text-blue-600 bg-white' : 'border-transparent text-gray-500 hover:text-gray-800 hover:bg-gray-50'" class="flex-shrink-0 w-32 md:w-auto md:flex-1 py-4 px-4 text-center border-b-2 font-medium text-sm relative transition-all duration-200">
                <span class="text-xl block mb-1 opacity-80">⏰</span> پیگیری
                {% if followups.count > 0 %}
                <span class="absolute top-2 right-2 md:right-1/4 bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">{{ followups.count }}</span>
                {% endif %}
            </button>
            <button @click="tab = 'visit'; window.history.replaceState(null, '', '?tab=visit')" :class="tab === 'visit' ? 'border-blue-600 text-blue-600 bg-white' : 'border-transparent text-gray-500 hover:text-gray-800 hover:bg-gray-50'" class="flex-shrink-0 w-32 md:w-auto md:flex-1 py-4 px-4 text-center border-b-2 font-medium text-sm transition-all duration-200">
                <span class="text-xl block mb-1 opacity-80">🏢</span> مراجعه
            </button>
            <button @click="tab = 'invoice'; window.history.replaceState(null, '', '?tab=invoice')" :class="tab === 'invoice' ? 'border-blue-600 text-blue-600 bg-white' : 'border-transparent text-gray-500 hover:text-gray-800 hover:bg-gray-50'" class="flex-shrink-0 w-32 md:w-auto md:flex-1 py-4 px-4 text-center border-b-2 font-medium text-sm transition-all duration-200">
                <span class="text-xl block mb-1 opacity-80">📄</span> فاکتورها
            </button>
        </div>
    </div>

    <!-- TAB 1: INFO -->
    <div x-show="tab === 'info'" x-transition.opacity class="space-y-6">
        <!-- Stats -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="bg-white p-4 rounded-2xl shadow-sm border-r-4 border-blue-500 flex flex-col justify-center">
                <span class="text-gray-500 text-xs mb-1">کل مشتریان</span>
                <span class="text-2xl font-bold text-gray-800">{{ customers|length }}</span>
            </div>
            <div class="bg-white p-4 rounded-2xl shadow-sm border-r-4 border-green-500 flex flex-col justify-center">
                <span class="text-gray-500 text-xs mb-1">سرنخ‌ها</span>
                <span class="text-2xl font-bold text-gray-800">{{ customers|length }}</span>
            </div>
            <div class="bg-white p-4 rounded-2xl shadow-sm border-r-4 border-orange-500 flex flex-col justify-center">
                <span class="text-gray-500 text-xs mb-1">در انتظار پیگیری</span>
                <span class="text-2xl font-bold text-gray-800">{{ followups|length }}</span>
            </div>
            <div class="bg-white p-4 rounded-2xl shadow-sm border-r-4 border-purple-500 flex flex-col justify-center">
                <span class="text-gray-500 text-xs mb-1">فاکتورهای اخیر</span>
                <span class="text-2xl font-bold text-gray-800">{{ invoices|length }}</span>
            </div>
        </div>

        <!-- Search & Actions -->
        <div class="flex flex-col md:flex-row justify-between gap-4 bg-white p-4 rounded-2xl shadow-sm">
            <form method="get" class="flex-1 flex gap-2">
                <input type="hidden" name="tab" value="info">
                <div class="relative w-full">
                    <span class="absolute right-3 top-2.5 text-gray-400">🔍</span>
                    <input type="text" name="q" value="{{ request.GET.q }}" placeholder="جستجوی نام یا شماره..." class="w-full pr-10 pl-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500 transition">
                </div>
                <button type="submit" class="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl shadow-sm font-medium transition">جستجو</button>
            </form>
            {% if 'customers.add' in user_permissions %}
            <a href="{% url 'customers:create' %}" class="px-6 py-2.5 bg-gray-900 hover:bg-gray-800 text-white rounded-xl shadow-sm font-medium flex items-center justify-center gap-2 transition whitespace-nowrap">
                <span>+</span> مشتری جدید
            </a>
            {% endif %}
        </div>
        
        <!-- Desktop Table -->
        <div class="hidden md:block bg-white rounded-2xl shadow-sm overflow-hidden border border-gray-100">
            <table class="w-full text-sm">
                <thead class="bg-gray-50/80 border-b border-gray-100">
                    <tr class="text-gray-600">
                        <th class="p-4 text-right font-medium">مشتری</th>
                        <th class="p-4 text-right font-medium">شماره تماس</th>
                        <th class="p-4 text-center font-medium">وضعیت</th>
                        <th class="p-4 text-center font-medium">نوع</th>
                        <th class="p-4 text-center font-medium">سرنخ</th>
                        <th class="p-4 text-left font-medium">عملیات</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-50">
                    {% for c in customers %}
                    <tr class="hover:bg-blue-50/30 transition group">
                        <td class="p-4 text-right">
                            <div class="flex items-center gap-3">
                                <div class="w-10 h-10 rounded-full bg-gradient-to-br from-blue-100 to-blue-200 text-blue-700 flex items-center justify-center font-bold text-lg">
                                    {{ c.name|first|upper }}
                                </div>
                                <div>
                                    <div class="font-bold text-gray-800 group-hover:text-blue-600 transition">{{ c.name }}</div>
                                    <div class="text-xs text-gray-400 mt-0.5">{{ c.created_at|jdate:"Y/m/d" }}</div>
                                </div>
                            </div>
                        </td>
                        <td class="p-4 text-right font-mono text-gray-600" dir="ltr">{{ c.mobile }}</td>
                        <td class="p-4 text-center">
                            {% if c.status == 'active' %}
                                <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-green-50 text-green-700 border border-green-100"><span class="w-1.5 h-1.5 rounded-full bg-green-500"></span>{{ c.get_status_display }}</span>
                            {% else %}
                                <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-gray-50 text-gray-600 border border-gray-200"><span class="w-1.5 h-1.5 rounded-full bg-gray-400"></span>{{ c.get_status_display }}</span>
                            {% endif %}
                        </td>
                        <td class="p-4 text-center text-gray-600 text-xs">{{ c.get_customer_type_display }}</td>
                        <td class="p-4 text-center">
                            {% if c.is_lead %}
                                <span class="bg-purple-100 text-purple-700 px-2 py-1 rounded-md text-[11px] font-bold">سرنخ</span>
                            {% else %}
                                <span class="text-gray-300">-</span>
                            {% endif %}
                        </td>
                        <td class="p-4 text-left">
                            <a href="{% url 'customers:detail' c.pk %}" class="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-white border border-gray-200 text-gray-500 hover:text-blue-600 hover:border-blue-300 hover:shadow-sm transition" title="جزئیات">
                                ↗
                            </a>
                        </td>
                    </tr>
                    {% empty %}
                    <tr><td colspan="6" class="p-12 text-center text-gray-400">هیچ مشتری یافت نشد.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- Mobile Cards -->
        <div class="md:hidden space-y-3">
            {% for c in customers %}
            <div class="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 relative overflow-hidden">
                <div class="absolute top-0 right-0 w-1 h-full {% if c.status == 'active' %}bg-green-500{% else %}bg-gray-300{% endif %}"></div>
                <div class="flex justify-between items-start mb-2">
                    <div class="flex items-center gap-2">
                        <div class="font-bold text-gray-800">{{ c.name }}</div>
                        {% if c.is_lead %}<span class="bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded text-[10px] font-bold">سرنخ</span>{% endif %}
                    </div>
                    <span class="text-[10px] text-gray-400">{{ c.created_at|jdate:"Y/m/d" }}</span>
                </div>
                <div class="font-mono text-gray-600 text-sm mb-3" dir="ltr">{{ c.mobile }}</div>
                <div class="flex gap-2 mb-4">
                    <span class="text-xs bg-gray-50 text-gray-600 px-2 py-1 rounded-md border border-gray-100">{{ c.get_status_display }}</span>
                    <span class="text-xs bg-gray-50 text-gray-600 px-2 py-1 rounded-md border border-gray-100">{{ c.get_customer_type_display }}</span>
                </div>
                <a href="{% url 'customers:detail' c.pk %}" class="block w-full text-center py-2 bg-blue-50 text-blue-700 rounded-xl text-sm font-medium active:bg-blue-100">مشاهده پروفایل</a>
            </div>
            {% empty %}
            <div class="bg-white rounded-2xl p-8 text-center text-gray-400">هیچ مشتری یافت نشد.</div>
            {% endfor %}
        </div>
    </div>

    <!-- TAB 2: CALL -->
    <div x-show="tab === 'call'" x-transition.opacity style="display: none;">
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden max-w-4xl mx-auto">
            <div class="bg-gradient-to-r from-blue-600 to-blue-800 p-6 text-white">
                <h2 class="text-xl font-bold">ثبت تماس / سرنخ جدید</h2>
                <p class="text-blue-100 text-sm mt-1">اطلاعات مکالمه را وارد کنید. در صورت نیاز، مشتری به پیگیری منتقل می‌شود.</p>
            </div>
            
            <form method="post" action="{% url 'customers:hub_submit_call' %}" class="p-6 space-y-6">
                {% csrf_token %}
                
                <!-- Phone Check -->
                <div class="bg-gray-50 p-4 rounded-xl border border-gray-200">
                    <label class="block text-sm font-bold text-gray-700 mb-2">شماره تماس <span class="text-red-500">*</span></label>
                    <div class="relative">
                        <input type="text" name="mobile" x-model="mobile" @input.debounce.500ms="checkMobile()" required
                               class="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:border-blue-500 focus:ring-0 text-lg font-mono tracking-wider transition-colors" dir="ltr" placeholder="09123456789">
                        <div x-show="checking" class="absolute left-4 top-4 text-blue-500 animate-spin">⏳</div>
                    </div>
                    
                    <!-- Alert if exists -->
                    <div x-show="existingCustomer" x-cloak class="mt-3 bg-yellow-50 border border-yellow-200 p-3 rounded-lg flex items-start gap-3">
                        <span class="text-xl">⚠️</span>
                        <div>
                            <p class="text-sm font-bold text-yellow-800">این شماره قبلاً ثبت شده است!</p>
                            <p class="text-xs text-yellow-700 mt-1">مشتری: <span x-text="existingCustomer?.name"></span> | وضعیت: <span x-text="existingCustomer?.type"></span></p>
                            <p class="text-xs text-yellow-600 mt-2 font-medium">در صورت ادامه، اطلاعات تماس جدید به این مشتری متصل می‌شود.</p>
                        </div>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1.5">نام و نام خانوادگی</label>
                        <input type="text" name="name" id="hub_call_name" class="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1.5">نوع تماس</label>
                        <select name="call_type" class="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white">
                            <option value="incoming">ورودی (چت دیوار، تماس مشتری...)</option>
                            <option value="outgoing">خروجی (تماس با مشتری)</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1.5">منبع تماس</label>
                        <select name="source" class="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white">
                            {% for src in call_form.source.field.queryset %}
                            <option value="{{ src.id }}">{{ src.label|default:src.phone_number }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1.5">نوع مشتری</label>
                        <select name="customer_type" x-model="customerType" class="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white">
                            <option value="none">فاقد شرایط</option>
                            <option value="cash">نقدی</option>
                            <option value="cheque">چک</option>
                            <option value="installment">قسطی</option>
                        </select>
                    </div>
                    
                    <!-- Dynamic Fields -->
                    <div x-show="customerType === 'installment'" x-transition x-cloak class="bg-blue-50 p-3 rounded-xl border border-blue-100">
                        <label class="block text-sm font-medium text-blue-800 mb-1.5">تعداد اقساط</label>
                        <input type="number" name="installments_count" min="1" class="w-full px-4 py-2 border border-blue-200 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white">
                    </div>
                    <div x-show="customerType === 'cheque'" x-transition x-cloak class="bg-blue-50 p-3 rounded-xl border border-blue-100">
                        <label class="block text-sm font-medium text-blue-800 mb-1.5">تعداد چک</label>
                        <input type="number" name="cheques_count" min="1" max="5" class="w-full px-4 py-2 border border-blue-200 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white">
                    </div>

                    <div class="md:col-span-2 border-t border-gray-100 pt-4 mt-2">
                        <label class="block text-sm font-medium text-gray-700 mb-1.5">وضعیت نهایی مشتری</label>
                        <div class="flex gap-4">
                            <label class="flex-1 cursor-pointer">
                                <input type="radio" name="status" value="lead" x-model="customerStatus" class="peer sr-only">
                                <div class="p-3 text-center border-2 rounded-xl border-gray-200 text-gray-500 peer-checked:border-orange-500 peer-checked:bg-orange-50 peer-checked:text-orange-700 font-medium transition">
                                    بالقوه (نیازمند پیگیری)
                                </div>
                            </label>
                            <label class="flex-1 cursor-pointer">
                                <input type="radio" name="status" value="active" x-model="customerStatus" class="peer sr-only">
                                <div class="p-3 text-center border-2 rounded-xl border-gray-200 text-gray-500 peer-checked:border-green-500 peer-checked:bg-green-50 peer-checked:text-green-700 font-medium transition">
                                    بالفعل (سرنخ)
                                </div>
                            </label>
                        </div>
                    </div>

                    <div x-show="customerStatus === 'lead'" x-transition x-cloak class="md:col-span-2 bg-orange-50 p-4 rounded-xl border border-orange-200">
                        <label class="block text-sm font-bold text-orange-800 mb-2">تاریخ پیگیری <span class="text-red-500">*</span></label>
                        <input type="text" name="follow_up_date" data-jdp placeholder="برای ماندن در تب پیگیری، تاریخ را وارد کنید" class="w-full px-4 py-2.5 border border-orange-300 rounded-lg focus:ring-2 focus:ring-orange-500 bg-white">
                    </div>
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1.5">توضیحات مکالمه <span class="text-red-500">*</span></label>
                    <textarea name="notes" rows="4" required class="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500" placeholder="جزئیات صحبت، نیازهای مشتری و ..."></textarea>
                </div>

                <div class="pt-4 border-t border-gray-100 flex gap-3">
                    <button type="submit" class="flex-1 py-3.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-lg shadow-md transition">ثبت تماس</button>
                </div>
            </form>
        </div>
    </div>

    <!-- TAB 3: FOLLOWUP -->
    <div x-show="tab === 'followup'" x-transition.opacity style="display: none;">
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            <div class="p-5 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
                <div>
                    <h2 class="font-bold text-gray-800 text-lg">پیگیری‌های در انتظار</h2>
                    <p class="text-xs text-gray-500 mt-1">مشتریانی که وضعیت بالقوه دارند و باید با آن‌ها تماس گرفته شود.</p>
                </div>
                <div class="bg-orange-100 text-orange-700 px-3 py-1 rounded-full font-bold text-sm">{{ followups.count }} مورد</div>
            </div>
            
            <div class="divide-y divide-gray-100">
                {% for f in followups %}
                <div class="p-4 md:p-5 hover:bg-gray-50 transition flex flex-col md:flex-row gap-4 items-start md:items-center">
                    <div class="flex-1">
                        <div class="flex items-center gap-2 mb-1">
                            <span class="font-bold text-gray-800 text-base">{{ f.customer.name }}</span>
                            <span class="text-xs font-mono bg-gray-100 text-gray-600 px-2 py-0.5 rounded" dir="ltr">{{ f.customer.mobile }}</span>
                        </div>
                        <div class="text-sm text-gray-600 line-clamp-1"><span class="text-gray-400">یادداشت:</span> {{ f.notes }}</div>
                    </div>
                    <div class="flex items-center gap-4 w-full md:w-auto">
                        <div class="text-left md:text-center flex-1 md:flex-none">
                            <div class="text-xs text-gray-400 mb-0.5">تاریخ پیگیری</div>
                            <div class="font-bold text-orange-600 text-sm">{{ f.follow_up_date|jdate:"Y/m/d" }}</div>
                        </div>
                        <a href="{% url 'calls:edit' f.pk %}" class="px-5 py-2.5 bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 hover:text-blue-600 hover:border-blue-300 rounded-xl text-sm font-medium shadow-sm transition flex items-center gap-2">
                            ✍️ ثبت نتیجه
                        </a>
                    </div>
                </div>
                {% empty %}
                <div class="p-12 text-center flex flex-col items-center">
                    <span class="text-5xl mb-3 opacity-50">🎉</span>
                    <p class="text-gray-500 font-medium">هیچ پیگیری در انتظاری وجود ندارد.</p>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>

    <!-- TAB 4: VISIT -->
    <div x-show="tab === 'visit'" x-transition.opacity style="display: none;">
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden max-w-3xl mx-auto">
            <div class="bg-gradient-to-r from-emerald-500 to-teal-600 p-6 text-white">
                <h2 class="text-xl font-bold">ثبت مراجعه حضوری</h2>
                <p class="text-emerald-50 text-sm mt-1">اگر مشتری به دفتر آمده است، اطلاعات مراجعه را ثبت کنید.</p>
            </div>
            
            <form method="post" action="{% url 'customers:hub_submit_visit' %}" class="p-6 space-y-5">
                {% csrf_token %}
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1.5">انتخاب مشتری <span class="text-red-500">*</span></label>
                    <select name="customer" required class="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 bg-white">
                        <option value="">-- جستجو و انتخاب کنید --</option>
                        {% for c in customers %}
                        <option value="{{ c.id }}">{{ c.name }} ({{ c.mobile }})</option>
                        {% endfor %}
                    </select>
                </div>
                
                <div class="bg-gray-50 p-5 rounded-xl border border-gray-200">
                    <label class="flex items-start gap-3 cursor-pointer">
                        <input type="checkbox" name="is_successful" class="w-6 h-6 text-emerald-600 rounded border-gray-300 focus:ring-emerald-500 mt-0.5">
                        <div>
                            <div class="font-bold text-gray-800">مراحل با موفقیت طی شد</div>
                            <div class="text-xs text-gray-500 mt-1">با تیک زدن این گزینه، پرونده مشتری تشکیل شده و به صفحه «پرونده» منتقل می‌شود.</div>
                        </div>
                    </label>
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1.5">یادداشت مراجعه <span class="text-red-500">*</span></label>
                    <textarea name="notes" rows="4" required class="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500" placeholder="نتیجه مراجعه، مدارک تحویل داده شده و ..."></textarea>
                </div>

                <div class="pt-2">
                    <button type="submit" class="w-full py-3.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-bold text-lg shadow-md transition">ثبت مراجعه</button>
                </div>
            </form>
        </div>
    </div>

    <!-- TAB 5: INVOICE -->
    <div x-show="tab === 'invoice'" x-transition.opacity style="display: none;">
        <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-4">
            <div>
                <h2 class="text-xl font-bold text-gray-800">مدیریت فاکتورها</h2>
                <p class="text-sm text-gray-500 mt-1">لیست آخرین فاکتورهای صادر شده در سیستم</p>
            </div>
            {% if 'invoices.add' in user_permissions %}
            <a href="{% url 'sales:create' %}" class="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-medium shadow-sm flex items-center gap-2 transition">
                <span>+</span> صدور فاکتور جدید
            </a>
            {% endif %}
        </div>
        
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            <table class="w-full text-sm">
                <thead class="bg-gray-50/80 border-b border-gray-100">
                    <tr class="text-gray-600">
                        <th class="p-4 text-right font-medium">شماره فاکتور</th>
                        <th class="p-4 text-right font-medium">مشتری</th>
                        <th class="p-4 text-left font-medium">مبلغ</th>
                        <th class="p-4 text-center font-medium">وضعیت</th>
                        <th class="p-4 text-right font-medium">تاریخ</th>
                        <th class="p-4 text-left font-medium">عملیات</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-50">
                    {% for inv in invoices %}
                    <tr class="hover:bg-blue-50/30 transition group">
                        <td class="p-4 text-right font-mono text-xs font-bold text-blue-600" dir="ltr">{{ inv.number }}</td>
                        <td class="p-4 text-right">
                            <div class="font-medium text-gray-800">{{ inv.customer.name }}</div>
                            <div class="text-xs text-gray-400 font-mono" dir="ltr">{{ inv.customer.mobile }}</div>
                        </td>
                        <td class="p-4 text-left font-bold text-gray-800" dir="ltr">{{ inv.total|floatformat:0 }} <span class="text-xs font-normal text-gray-400">تومان</span></td>
                        <td class="p-4 text-center">
                            {% if inv.status == 'paid' %}<span class="bg-green-100 text-green-700 px-2 py-1 rounded text-xs">{{ inv.get_status_display }}</span>
                            {% elif inv.status == 'issued' %}<span class="bg-blue-100 text-blue-700 px-2 py-1 rounded text-xs">{{ inv.get_status_display }}</span>
                            {% else %}<span class="bg-gray-100 text-gray-700 px-2 py-1 rounded text-xs">{{ inv.get_status_display }}</span>{% endif %}
                        </td>
                        <td class="p-4 text-right text-xs text-gray-500">{{ inv.issue_date|jdate:"Y/m/d" }}</td>
                        <td class="p-4 text-left">
                            <a href="{% url 'sales:detail' inv.pk %}" class="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-white border border-gray-200 text-gray-500 hover:text-blue-600 hover:border-blue-300 hover:shadow-sm transition" title="مشاهده">
                                ↗
                            </a>
                        </td>
                    </tr>
                    {% empty %}
                    <tr><td colspan="6" class="p-12 text-center text-gray-400">هیچ فاکتوری یافت نشد.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

</div>

<style>
    /* Hide scrollbar for tabs but keep functionality */
    .hide-scrollbar::-webkit-scrollbar { display: none; }
    .hide-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
</style>
{% endblock %}
"""
    write_file('templates/customers/hub.html', html)

# ═══════════════════════════════════════════════════════════
# 5. Execute Everything
# ═══════════════════════════════════════════════════════════
def main():
    print("🚀 Starting Major Upgrade V2 (Premium Hub & Route Merging)...\n")
    create_api()
    merge_routes()
    update_base_html()
    create_hub_template()
    
    print("\n🎉 Success! Server restart recommended.")
    print("👉 All old routes (Customers, Calls, Invoices) now redirect to the new unified Hub.")

if __name__ == '__main__':
    main()
