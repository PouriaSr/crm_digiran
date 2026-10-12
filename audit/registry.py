"""
رجیستری مدل‌های تحت رصد — فاز ۸.۴
"""

AUDIT_MODELS = {
    # ─── مشتریان ───
    'customers.Customer': [
        'name', 'mobile', 'email', 'national_id',
        'status', 'source', 'assigned_to',
    ],
    'customers.CustomerNote': [
        'text', 'is_pinned',
    ],

    # ─── کالاها ───
    'products.Product': [
        'name', 'code', 'price', 'cost_price',
        'stock', 'min_stock', 'is_active', 'is_deleted',
    ],
    'products.Category': [
        'name', 'slug', 'is_active',
    ],

    # ─── منابع انسانی ───
    'hr.Employee': [
        'first_name', 'last_name', 'national_id', 'mobile',
        'position', 'contract_type', 'is_active',
    ],
    'hr.Task': [
        'title', 'status', 'priority', 'due_date',
    ],
    'hr.LeaveRequest': [
        'status', 'leave_type',
    ],

    # ─── کاربران ───
    'auth.User': [
        'username', 'email', 'first_name', 'last_name',
        'is_active', 'is_staff', 'is_superuser',
    ],

    # ─── تبلیغات ───
    'ads.Ad': [
        'platform', 'process', 'cost', 'source',
        'product', 'ad_number', 'note',
    ],
    'ads.AdPlatform': [
        'name', 'is_active',
    ],
    'ads.AdProcess': [
        'platform', 'name', 'default_cost', 'is_active',
    ],
    'ads.AdSource': [
        'phone_number', 'label', 'is_active',
    ],
}