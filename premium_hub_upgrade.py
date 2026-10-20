#!/usr/bin/env python3
"""
Premium UI/UX Upgrade for Customer Hub.
Includes: Smart FAB, Glassmorphism UI, KPI Cards, Quick Actions, and UX improvements.
"""
import os
import shutil
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
BACKUP_DIR = BASE / f'.premium_hub_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'

def backup_file(path):
    if not path.exists(): return
    rel = path.relative_to(BASE)
    dest = BACKUP_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)

def write_file(rel_path, content):
    p = BASE / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists(): backup_file(p)
    p.write_text(content.lstrip("\n"), encoding='utf-8')
    print(f"  OK Created/Updated: {rel_path}")

# ═══════════════════════════════════════════════════════════
# 1. Update Views (Add KPIs)
# ═══════════════════════════════════════════════════════════
def update_views():
    path = 'customers/hub_views.py'
    content = Path(BASE / path).read_text(encoding='utf-8')
    
    # Simple replacement to add stats to context
    old_context = "    context = {\n        'active_tab': tab,"
    new_context = """    from django.db.models import Sum
    from datetime import date
    
    total_customers = Customer.objects.count()
    total_leads = Customer.objects.filter(is_lead=True).count()
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
        },"""
    
    if old_context in content:
        content = content.replace(old_context, new_context)
        write_file(path, content)
    else:
        print(f"  ! Could not patch views context, skipping.")

# ═══════════════════════════════════════════════════════════
# 2. The Massive Premium Template
# ═══════════════════════════════════════════════════════════
def create_premium_template():
    html = r"""{% extends 'base.html' %}
{% load fa_numbers %}

{% block title %}مرکز مشتریان{% endblock %}
{% block mobile_title %}مرکز مشتریان{% endblock %}

{% block extra_head %}
<style>
    .glass-panel {
        background: rgba(255, 255, 255, 0.7);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.5);
    }
    .tab-active {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        color: white !important;
        box-shadow: 0 10px 15px -3px rgba(37, 99, 235, 0.3);
        transform: translateY(-2px);
    }
    .hide-scrollbar::-webkit-scrollbar { display: none; }
    .hide-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
    
    @keyframes slideUp {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .animate-slide-up { animation: slideUp 0.3s ease-out forwards; }
    
    @keyframes pulse-ring {
        0% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.5); }
        70% { box-shadow: 0 0 0 10px rgba(37, 99, 235, 0); }
        100% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0); }
    }
    .pulse-ring { animation: pulse-ring 2s infinite; }
</style>
{% endblock %}

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
                fetch('{% url "customers:hub_check_api" %}?mobile=' + this.mobile)
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
     }" class="max-w-7xl mx-auto pb-24 relative">
    
    <!-- KPI Stats (Visible only on Info Tab) -->
    <div x-show="tab === 'info'" x-transition.opacity class="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-5 mb-6">
        <div class="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 flex items-center gap-4 group hover:shadow-md transition">
            <div class="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center text-2xl group-hover:scale-110 transition">👥</div>
            <div>
                <div class="text-xs text-gray-500 font-medium mb-0.5">کل مشتریان</div>
                <div class="text-2xl font-bold text-gray-800">{{ stats.total_customers|fa_num }}</div>
            </div>
        </div>
        <div class="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 flex items-center gap-4 group hover:shadow-md transition">
            <div class="w-12 h-12 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center text-2xl group-hover:scale-110 transition">⭐</div>
            <div>
                <div class="text-xs text-gray-500 font-medium mb-0.5">تعداد سرنخ‌ها</div>
                <div class="text-2xl font-bold text-gray-800">{{ stats.total_leads|fa_num }}</div>
            </div>
        </div>
        <div class="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 flex items-center gap-4 group hover:shadow-md transition">
            <div class="w-12 h-12 rounded-xl bg-orange-50 text-orange-600 flex items-center justify-center text-2xl group-hover:scale-110 transition">⏰</div>
            <div>
                <div class="text-xs text-gray-500 font-medium mb-0.5">پیگیری‌های معوق</div>
                <div class="text-2xl font-bold text-gray-800">{{ stats.pending_followups|fa_num }}</div>
            </div>
        </div>
        <div class="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 flex items-center gap-4 group hover:shadow-md transition">
            <div class="w-12 h-12 rounded-xl bg-green-50 text-green-600 flex items-center justify-center text-2xl group-hover:scale-110 transition">💰</div>
            <div>
                <div class="text-xs text-gray-500 font-medium mb-0.5">درآمد وصول شده</div>
                <div class="text-lg font-bold text-gray-800" dir="ltr">{{ stats.recent_revenue|floatformat:0|fa_num }} <span class="text-xs font-normal">تومان</span></div>
            </div>
        </div>
    </div>

    <!-- Premium Tabs -->
    <div class="bg-white/80 backdrop-blur-md rounded-2xl shadow-sm border border-gray-100 mb-6 p-1.5 sticky top-14 lg:top-0 z-30">
        <div class="flex overflow-x-auto hide-scrollbar gap-1 md:gap-2">
            <button @click="tab = 'info'; window.history.replaceState(null, '', '?tab=info')" 
                    :class="tab === 'info' ? 'tab-active' : 'text-gray-500 hover:bg-gray-100'"
                    class="flex-shrink-0 w-24 md:w-auto md:flex-1 py-3 px-2 rounded-xl flex flex-col md:flex-row items-center justify-center gap-1 md:gap-2 transition-all duration-300">
                <span class="text-xl md:text-lg">👥</span>
                <span class="font-bold text-[11px] md:text-sm">اطلاعات</span>
            </button>
            
            <button @click="tab = 'call'; window.history.replaceState(null, '', '?tab=call')" 
                    :class="tab === 'call' ? 'tab-active' : 'text-gray-500 hover:bg-gray-100'"
                    class="flex-shrink-0 w-24 md:w-auto md:flex-1 py-3 px-2 rounded-xl flex flex-col md:flex-row items-center justify-center gap-1 md:gap-2 transition-all duration-300">
                <span class="text-xl md:text-lg">📞</span>
                <span class="font-bold text-[11px] md:text-sm">تماس</span>
            </button>
            
            <button @click="tab = 'followup'; window.history.replaceState(null, '', '?tab=followup')" 
                    :class="tab === 'followup' ? 'tab-active' : 'text-gray-500 hover:bg-gray-100'"
                    class="flex-shrink-0 w-24 md:w-auto md:flex-1 py-3 px-2 rounded-xl relative flex flex-col md:flex-row items-center justify-center gap-1 md:gap-2 transition-all duration-300">
                <span class="text-xl md:text-lg">⏰</span>
                <span class="font-bold text-[11px] md:text-sm">پیگیری</span>
                {% if stats.pending_followups > 0 %}
                <span :class="tab === 'followup' ? 'bg-white text-blue-600' : 'bg-red-500 text-white'" class="absolute top-1 right-1 md:static md:ml-1 text-[10px] font-bold px-1.5 py-0.5 rounded-full">{{ stats.pending_followups|fa_num }}</span>
                {% endif %}
            </button>
            
            <button @click="tab = 'visit'; window.history.replaceState(null, '', '?tab=visit')" 
                    :class="tab === 'visit' ? 'tab-active' : 'text-gray-500 hover:bg-gray-100'"
                    class="flex-shrink-0 w-24 md:w-auto md:flex-1 py-3 px-2 rounded-xl flex flex-col md:flex-row items-center justify-center gap-1 md:gap-2 transition-all duration-300">
                <span class="text-xl md:text-lg">🏢</span>
                <span class="font-bold text-[11px] md:text-sm">مراجعه</span>
            </button>
            
            <button @click="tab = 'invoice'; window.history.replaceState(null, '', '?tab=invoice')" 
                    :class="tab === 'invoice' ? 'tab-active' : 'text-gray-500 hover:bg-gray-100'"
                    class="flex-shrink-0 w-24 md:w-auto md:flex-1 py-3 px-2 rounded-xl flex flex-col md:flex-row items-center justify-center gap-1 md:gap-2 transition-all duration-300">
                <span class="text-xl md:text-lg">📄</span>
                <span class="font-bold text-[11px] md:text-sm">فاکتورها</span>
            </button>
        </div>
    </div>

    <!-- Dynamic Content Area -->
    <div class="relative">
        
        <!-- TAB 1: INFO -->
        <div x-show="tab === 'info'" x-transition:enter="animate-slide-up" class="space-y-4">
            <div class="flex flex-col md:flex-row justify-between items-center gap-3">
                <form method="get" class="w-full md:w-1/2 relative">
                    <input type="hidden" name="tab" value="info">
                    <input type="text" name="q" value="{{ request.GET.q }}" placeholder="جستجوی نام یا شماره..." class="w-full pl-12 pr-4 py-3 bg-white border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 shadow-sm transition-all text-sm">
                    <button type="submit" class="absolute left-2 top-1/2 -translate-y-1/2 w-8 h-8 flex items-center justify-center bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition">🔍</button>
                </form>
            </div>
            
            <!-- Desktop Table -->
            <div class="hidden md:block bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                <table class="w-full text-sm">
                    <thead class="bg-gray-50/50">
                        <tr class="text-gray-500 border-b border-gray-100">
                            <th class="p-4 text-right font-medium w-1/3">مشتری</th>
                            <th class="p-4 text-right font-medium">شماره تماس</th>
                            <th class="p-4 text-center font-medium">وضعیت</th>
                            <th class="p-4 text-center font-medium">نوع</th>
                            <th class="p-4 text-center font-medium">عملیات</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-50">
                        {% for c in customers %}
                        <tr class="hover:bg-blue-50/30 transition group">
                            <td class="p-4 text-right">
                                <div class="flex items-center gap-3">
                                    <div class="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white flex items-center justify-center font-bold text-lg shadow-sm">
                                        {{ c.name|first|upper }}
                                    </div>
                                    <div>
                                        <div class="font-bold text-gray-800 group-hover:text-blue-600 transition flex items-center gap-2">
                                            {{ c.name }}
                                            {% if c.is_lead %}<span class="bg-purple-100 text-purple-700 px-2 py-0.5 rounded text-[10px] font-bold">سرنخ</span>{% endif %}
                                        </div>
                                        <div class="text-xs text-gray-400 mt-0.5">{{ c.created_at|jdate:"Y/m/d" }}</div>
                                    </div>
                                </div>
                            </td>
                            <td class="p-4 text-right">
                                <div class="font-mono text-gray-700 bg-gray-50 px-2 py-1 rounded inline-block" dir="ltr">{{ c.mobile }}</div>
                            </td>
                            <td class="p-4 text-center">
                                {% if c.status == 'active' %}
                                    <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-green-50 text-green-700"><span class="w-1.5 h-1.5 rounded-full bg-green-500"></span>{{ c.get_status_display }}</span>
                                {% else %}
                                    <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600"><span class="w-1.5 h-1.5 rounded-full bg-gray-400"></span>{{ c.get_status_display }}</span>
                                {% endif %}
                            </td>
                            <td class="p-4 text-center text-gray-600 text-xs font-medium">{{ c.get_customer_type_display }}</td>
                            <td class="p-4 text-center">
                                <div class="flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <a href="tel:{{ c.mobile }}" class="w-8 h-8 rounded-lg bg-green-50 text-green-600 flex items-center justify-center hover:bg-green-100" title="تماس">📞</a>
                                    <a href="{% url 'customers:detail' c.pk %}" class="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center hover:bg-blue-100" title="پروفایل">👤</a>
                                    <a href="{% url 'customers:edit' c.pk %}" class="w-8 h-8 rounded-lg bg-gray-50 text-gray-600 flex items-center justify-center hover:bg-gray-200" title="ویرایش">✏️</a>
                                </div>
                            </td>
                        </tr>
                        {% empty %}
                        <tr><td colspan="5" class="p-12 text-center text-gray-400">هیچ مشتری یافت نشد.</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>

            <!-- Mobile Cards -->
            <div class="md:hidden space-y-3">
                {% for c in customers %}
                <div class="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 relative">
                    <div class="flex justify-between items-start mb-2">
                        <div class="flex items-center gap-2">
                            <div class="font-bold text-gray-800 text-lg">{{ c.name }}</div>
                            {% if c.is_lead %}<span class="bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded text-[10px] font-bold">سرنخ</span>{% endif %}
                        </div>
                        <span class="text-[10px] bg-gray-50 text-gray-500 px-2 py-1 rounded-md">{{ c.get_customer_type_display }}</span>
                    </div>
                    <div class="flex items-center gap-3 mb-4">
                        <div class="font-mono text-gray-700 text-sm bg-gray-50 px-2 py-1 rounded inline-block" dir="ltr">{{ c.mobile }}</div>
                        <span class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[10px] font-medium {% if c.status == 'active' %}bg-green-50 text-green-700{% else %}bg-gray-100 text-gray-600{% endif %}">
                            {{ c.get_status_display }}
                        </span>
                    </div>
                    <div class="flex gap-2">
                        <a href="tel:{{ c.mobile }}" class="flex-1 py-2.5 bg-green-50 text-green-700 rounded-xl text-sm font-bold flex items-center justify-center gap-2">📞 تماس</a>
                        <a href="{% url 'customers:detail' c.pk %}" class="flex-1 py-2.5 bg-blue-50 text-blue-700 rounded-xl text-sm font-bold flex items-center justify-center gap-2">پروفایل</a>
                    </div>
                </div>
                {% empty %}
                <div class="bg-white rounded-2xl p-8 text-center text-gray-400">هیچ مشتری یافت نشد.</div>
                {% endfor %}
            </div>
        </div>

        <!-- TAB 2: CALL -->
        <div x-show="tab === 'call'" x-transition:enter="animate-slide-up" style="display: none;">
            <div class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden max-w-4xl mx-auto">
                <div class="bg-gradient-to-r from-blue-600 to-indigo-700 p-6 text-white flex items-center gap-4">
                    <div class="w-12 h-12 bg-white/20 rounded-2xl flex items-center justify-center text-2xl backdrop-blur-sm">📞</div>
                    <div>
                        <h2 class="text-xl font-bold">ثبت تماس / سرنخ جدید</h2>
                        <p class="text-blue-100 text-sm mt-1">اطلاعات مکالمه را وارد کنید تا سیستم به‌روزرسانی شود.</p>
                    </div>
                </div>
                
                <form method="post" action="{% url 'customers:hub_submit_call' %}" class="p-6 md:p-8 space-y-6">
                    {% csrf_token %}
                    
                    <!-- Smart Phone Check -->
                    <div class="relative">
                        <label class="block text-sm font-bold text-gray-700 mb-2">شماره تماس <span class="text-red-500">*</span></label>
                        <div class="relative">
                            <input type="text" name="mobile" x-model="mobile" @input.debounce.400ms="checkMobile()" required
                                   class="w-full px-5 py-4 border-2 border-gray-200 rounded-2xl focus:border-blue-500 focus:ring-4 focus:ring-blue-100 text-xl font-mono tracking-widest transition-all" dir="ltr" placeholder="09123456789">
                            
                            <div x-show="checking" class="absolute left-4 top-1/2 -translate-y-1/2 text-blue-500">
                                <svg class="animate-spin h-6 w-6" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                            </div>
                            
                            <div x-show="!checking && existingCustomer" x-cloak class="absolute left-4 top-1/2 -translate-y-1/2 text-yellow-500 text-2xl">⚠️</div>
                            <div x-show="!checking && !existingCustomer && mobile.length >= 10" x-cloak class="absolute left-4 top-1/2 -translate-y-1/2 text-green-500 text-2xl">✅</div>
                        </div>
                        
                        <!-- Alert if exists -->
                        <div x-show="existingCustomer" x-cloak x-transition class="mt-3 bg-yellow-50 border border-yellow-200 p-4 rounded-xl flex items-start gap-3 shadow-sm">
                            <span class="text-2xl">⚠️</span>
                            <div>
                                <p class="text-sm font-bold text-yellow-800">این شماره در سیستم موجود است!</p>
                                <p class="text-xs text-yellow-700 mt-1">مشتری: <span class="font-bold" x-text="existingCustomer?.name"></span> | نوع: <span x-text="existingCustomer?.type"></span></p>
                                <p class="text-xs text-yellow-600 mt-2">با ادامه، این تماس به سوابق ایشان اضافه می‌شود.</p>
                            </div>
                        </div>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1.5">نام و نام خانوادگی</label>
                            <input type="text" name="name" id="hub_call_name" class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500 transition-colors">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1.5">نوع تماس</label>
                            <select name="call_type" class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500 transition-colors">
                                <option value="incoming">ورودی (چت دیوار، تماس مشتری...)</option>
                                <option value="outgoing">خروجی (تماس با مشتری)</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1.5">منبع تماس</label>
                            <select name="source" class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500 transition-colors">
                                {% for src in call_form.source.field.queryset %}
                                <option value="{{ src.id }}">{{ src.label|default:src.phone_number }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1.5">نوع مشتری</label>
                            <select name="customer_type" x-model="customerType" class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500 transition-colors">
                                <option value="none">فاقد شرایط</option>
                                <option value="cash">نقدی</option>
                                <option value="cheque">چک</option>
                                <option value="installment">قسطی</option>
                            </select>
                        </div>
                        
                        <!-- Dynamic Fields -->
                        <div x-show="customerType === 'installment'" x-transition x-cloak class="md:col-span-2 bg-indigo-50 p-4 rounded-xl border border-indigo-100 flex items-center gap-4">
                            <label class="text-sm font-bold text-indigo-800">تعداد اقساط:</label>
                            <input type="number" name="installments_count" min="1" class="flex-1 px-4 py-2 border border-indigo-200 rounded-lg focus:ring-2 focus:ring-indigo-500 bg-white" placeholder="مثلاً 12">
                        </div>
                        <div x-show="customerType === 'cheque'" x-transition x-cloak class="md:col-span-2 bg-indigo-50 p-4 rounded-xl border border-indigo-100 flex items-center gap-4">
                            <label class="text-sm font-bold text-indigo-800">تعداد چک:</label>
                            <input type="number" name="cheques_count" min="1" max="5" class="flex-1 px-4 py-2 border border-indigo-200 rounded-lg focus:ring-2 focus:ring-indigo-500 bg-white" placeholder="بین 1 تا 5">
                        </div>

                        <div class="md:col-span-2 border-t border-gray-100 pt-5 mt-2">
                            <label class="block text-sm font-bold text-gray-700 mb-3">وضعیت نهایی مشتری</label>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <label class="relative cursor-pointer">
                                    <input type="radio" name="status" value="lead" x-model="customerStatus" class="peer sr-only">
                                    <div class="p-4 rounded-xl border-2 border-gray-200 bg-white flex items-center gap-3 peer-checked:border-orange-500 peer-checked:bg-orange-50 peer-checked:shadow-sm transition-all">
                                        <div class="w-10 h-10 rounded-full bg-orange-100 text-orange-600 flex items-center justify-center text-xl peer-checked:bg-orange-500 peer-checked:text-white">⏰</div>
                                        <div>
                                            <div class="font-bold text-gray-800">بالقوه (نیازمند پیگیری)</div>
                                            <div class="text-xs text-gray-500 mt-0.5">به تب پیگیری منتقل می‌شود</div>
                                        </div>
                                    </div>
                                </label>
                                <label class="relative cursor-pointer">
                                    <input type="radio" name="status" value="active" x-model="customerStatus" class="peer sr-only">
                                    <div class="p-4 rounded-xl border-2 border-gray-200 bg-white flex items-center gap-3 peer-checked:border-green-500 peer-checked:bg-green-50 peer-checked:shadow-sm transition-all">
                                        <div class="w-10 h-10 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-xl">⭐</div>
                                        <div>
                                            <div class="font-bold text-gray-800">بالفعل (سرنخ)</div>
                                            <div class="text-xs text-gray-500 mt-0.5">در لیست سرنخ‌ها تگ می‌خورد</div>
                                        </div>
                                    </div>
                                </label>
                            </div>
                        </div>

                        <div x-show="customerStatus === 'lead'" x-transition x-cloak class="md:col-span-2 bg-orange-50 p-5 rounded-xl border border-orange-200">
                            <label class="block text-sm font-bold text-orange-800 mb-2 flex items-center gap-2">
                                تاریخ پیگیری <span class="text-red-500">*</span>
                            </label>
                            <input type="text" name="follow_up_date" data-jdp placeholder="۱۴۰۵/۰۱/۱۵" class="w-full px-4 py-3 border border-orange-300 rounded-xl focus:ring-4 focus:ring-orange-100 bg-white text-center font-bold text-lg">
                        </div>
                    </div>

                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1.5">توضیحات مکالمه <span class="text-red-500">*</span></label>
                        <textarea name="notes" rows="3" required class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500 transition-colors resize-none" placeholder="خلاصه صحبت، نیازها و ..."></textarea>
                    </div>

                    <div class="pt-2">
                        <button type="submit" class="w-full py-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white rounded-xl font-bold text-lg shadow-lg shadow-blue-200 transition transform active:scale-[0.99] flex items-center justify-center gap-2">
                            <span>💾</span> ثبت نهایی تماس
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <!-- TAB 3: FOLLOWUP (Timeline) -->
        <div x-show="tab === 'followup'" x-transition:enter="animate-slide-up" style="display: none;">
            <div class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                <div class="p-6 border-b border-gray-100 bg-gradient-to-r from-orange-50 to-white flex justify-between items-center">
                    <div>
                        <h2 class="font-bold text-gray-800 text-lg flex items-center gap-2"><span class="text-orange-500">⏰</span> پیگیری‌های در انتظار</h2>
                        <p class="text-xs text-gray-500 mt-1">مشتریانی که وضعیت بالقوه دارند و باید با آن‌ها تماس گرفته شود.</p>
                    </div>
                    <div class="bg-orange-100 text-orange-700 px-4 py-2 rounded-xl font-bold text-sm shadow-sm">{{ followups.count }} مورد</div>
                </div>
                
                <div class="p-4 md:p-6 space-y-4">
                    {% for f in followups %}
                    <div class="bg-white border border-gray-100 rounded-xl p-4 md:p-5 shadow-sm hover:shadow-md transition group relative overflow-hidden">
                        <div class="absolute top-0 right-0 w-1.5 h-full bg-orange-400"></div>
                        <div class="flex flex-col md:flex-row gap-4 justify-between items-start md:items-center">
                            <div class="flex items-start gap-4 flex-1">
                                <div class="w-12 h-12 rounded-full bg-orange-100 text-orange-600 flex items-center justify-center text-xl font-bold flex-shrink-0">
                                    {{ f.customer.name|first|upper }}
                                </div>
                                <div>
                                    <div class="flex items-center gap-2 mb-1">
                                        <span class="font-bold text-gray-800 text-lg">{{ f.customer.name }}</span>
                                        <span class="text-xs font-mono bg-gray-100 text-gray-600 px-2 py-0.5 rounded" dir="ltr">{{ f.customer.mobile }}</span>
                                    </div>
                                    <div class="text-sm text-gray-600 line-clamp-2 bg-gray-50 p-2 rounded-lg"><span class="text-gray-400 text-xs block mb-1">یادداشت قبلی:</span> {{ f.notes }}</div>
                                </div>
                            </div>
                            <div class="flex items-center gap-4 w-full md:w-auto mt-2 md:mt-0 pt-3 md:pt-0 border-t md:border-t-0 border-gray-100">
                                <div class="text-left md:text-center flex-1 md:flex-none">
                                    <div class="text-xs text-gray-400 mb-0.5">تاریخ مقرر</div>
                                    <div class="font-bold text-orange-600 text-sm bg-orange-50 px-3 py-1 rounded-lg border border-orange-100">{{ f.follow_up_date|jdate:"Y/m/d" }}</div>
                                </div>
                                <a href="{% url 'calls:edit' f.pk %}" class="px-5 py-2.5 bg-gray-900 text-white hover:bg-gray-800 rounded-xl text-sm font-bold shadow-sm transition flex items-center gap-2 flex-shrink-0">
                                    ✍️ ثبت نتیجه
                                </a>
                            </div>
                        </div>
                    </div>
                    {% empty %}
                    <div class="text-center py-16 flex flex-col items-center">
                        <div class="w-24 h-24 bg-green-50 text-green-500 rounded-full flex items-center justify-center text-5xl mb-4">🎉</div>
                        <h3 class="text-lg font-bold text-gray-800">عالی!</h3>
                        <p class="text-gray-500 mt-1">هیچ پیگیری عقب‌افتاده‌ای وجود ندارد.</p>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>

        <!-- TAB 4: VISIT -->
        <div x-show="tab === 'visit'" x-transition:enter="animate-slide-up" style="display: none;">
            <div class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden max-w-3xl mx-auto">
                <div class="bg-gradient-to-r from-emerald-500 to-teal-600 p-6 text-white flex items-center gap-4">
                    <div class="w-12 h-12 bg-white/20 rounded-2xl flex items-center justify-center text-2xl backdrop-blur-sm">🏢</div>
                    <div>
                        <h2 class="text-xl font-bold">ثبت مراجعه حضوری</h2>
                        <p class="text-emerald-50 text-sm mt-1">اگر مشتری به دفتر آمده است، اطلاعات مراجعه را ثبت کنید.</p>
                    </div>
                </div>
                
                <form method="post" action="{% url 'customers:hub_submit_visit' %}" class="p-6 md:p-8 space-y-6">
                    {% csrf_token %}
                    <div>
                        <label class="block text-sm font-bold text-gray-700 mb-2">انتخاب مشتری <span class="text-red-500">*</span></label>
                        <select name="customer" required class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-emerald-500 transition-colors">
                            <option value="">-- جستجو و انتخاب کنید --</option>
                            {% for c in customers %}
                            <option value="{{ c.id }}">{{ c.name }} ({{ c.mobile }})</option>
                            {% endfor %}
                        </select>
                    </div>
                    
                    <div class="bg-emerald-50 p-5 rounded-xl border border-emerald-200">
                        <label class="flex items-start gap-4 cursor-pointer">
                            <input type="checkbox" name="is_successful" class="w-6 h-6 text-emerald-600 rounded border-emerald-300 focus:ring-emerald-500 mt-0.5">
                            <div>
                                <div class="font-bold text-emerald-900 text-base">مراحل با موفقیت طی شد</div>
                                <div class="text-sm text-emerald-700 mt-1 leading-relaxed">با تیک زدن این گزینه، پرونده مشتری تشکیل شده و به صفحه «پرونده» منتقل می‌شود.</div>
                            </div>
                        </label>
                    </div>

                    <div>
                        <label class="block text-sm font-bold text-gray-700 mb-2">یادداشت مراجعه <span class="text-red-500">*</span></label>
                        <textarea name="notes" rows="4" required class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-emerald-500 transition-colors resize-none" placeholder="نتیجه مراجعه، مدارک تحویل داده شده و ..."></textarea>
                    </div>

                    <div class="pt-2">
                        <button type="submit" class="w-full py-4 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white rounded-xl font-bold text-lg shadow-lg shadow-emerald-200 transition transform active:scale-[0.99]">
                            ثبت مراجعه
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <!-- TAB 5: INVOICE -->
        <div x-show="tab === 'invoice'" x-transition:enter="animate-slide-up" style="display: none;">
            <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-5">
                <div>
                    <h2 class="text-xl font-bold text-gray-800">مدیریت فاکتورها</h2>
                    <p class="text-sm text-gray-500 mt-1">لیست آخرین فاکتورهای صادر شده در سیستم</p>
                </div>
                {% if 'invoices.add' in user_permissions %}
                <a href="{% url 'sales:create' %}" class="px-5 py-2.5 bg-gray-900 hover:bg-gray-800 text-white rounded-xl text-sm font-bold shadow-sm flex items-center gap-2 transition">
                    <span>+</span> صدور فاکتور جدید
                </a>
                {% endif %}
            </div>
            
            <div class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                <table class="w-full text-sm hidden md:table">
                    <thead class="bg-gray-50/50 border-b border-gray-100">
                        <tr class="text-gray-500">
                            <th class="p-4 text-right font-medium">شماره فاکتور</th>
                            <th class="p-4 text-right font-medium">مشتری</th>
                            <th class="p-4 text-left font-medium">مبلغ</th>
                            <th class="p-4 text-center font-medium">وضعیت</th>
                            <th class="p-4 text-right font-medium">تاریخ</th>
                            <th class="p-4 text-center font-medium">عملیات</th>
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
                            <td class="p-4 text-center">
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

                <!-- Mobile Cards for Invoices -->
                <div class="md:hidden divide-y divide-gray-100">
                    {% for inv in invoices %}
                    <div class="p-4 flex flex-col gap-2">
                        <div class="flex justify-between items-center">
                            <span class="font-mono text-xs font-bold text-blue-600 bg-blue-50 px-2 py-1 rounded">{{ inv.number }}</span>
                            <span class="text-xs text-gray-400">{{ inv.issue_date|jdate:"Y/m/d" }}</span>
                        </div>
                        <div class="flex justify-between items-center">
                            <div class="font-bold text-gray-800">{{ inv.customer.name }}</div>
                            <span class="text-xs {% if inv.status == 'paid' %}text-green-600{% else %}text-gray-500{% endif %}">{{ inv.get_status_display }}</span>
                        </div>
                        <div class="flex justify-between items-center mt-1">
                            <div class="text-lg font-bold text-gray-900" dir="ltr">{{ inv.total|floatformat:0 }} <span class="text-xs font-normal text-gray-500">تومان</span></div>
                            <a href="{% url 'sales:detail' inv.pk %}" class="text-sm text-blue-600 font-medium">جزئیات ←</a>
                        </div>
                    </div>
                    {% empty %}
                    <div class="p-8 text-center text-gray-400">فاکتوری یافت نشد.</div>
                    {% endfor %}
                </div>
            </div>
        </div>

    </div>

    <!-- Smart FAB -->
    <div class="md:hidden fixed bottom-20 left-4 z-40">
        <button @click="
            if(tab === 'info') window.location.href='{% url 'customers:create' %}';
            else if(tab === 'call') document.querySelector('input[name=mobile]').focus();
            else if(tab === 'followup') tab = 'call';
            else if(tab === 'visit') tab = 'visit';
            else if(tab === 'invoice') window.location.href='{% url 'sales:create' %}';
        " class="w-14 h-14 bg-gradient-to-br from-blue-600 to-indigo-600 text-white rounded-full flex items-center justify-center text-3xl shadow-lg shadow-blue-500/50 pulse-ring transition transform active:scale-95">
            <span x-show="tab === 'info'">+</span>
            <span x-show="tab === 'call'">📞</span>
            <span x-show="tab === 'followup'">📞</span>
            <span x-show="tab === 'visit'">📝</span>
            <span x-show="tab === 'invoice'">+</span>
        </button>
    </div>

</div>
{% endblock %}
"""
    write_file('templates/customers/hub.html', html)

def main():
    print("🚀 Starting Premium UI/UX Upgrade for Customer Hub...\n")
    BACKUP_DIR.mkdir(exist_ok=True)
    update_views()
    create_premium_template()
    
    print(f"\n🎉 Success! Backup in {BACKUP_DIR.name}")
    print("Restart your server and hard-refresh browser (Ctrl+Shift+R).")

if __name__ == '__main__':
    main()
