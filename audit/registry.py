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

    # ─── تماس‌ها ───
    'calls.Call': [
        'contact_type', 'status', 'notes', 'follow_up_date',
        'is_followed_up', 'called_by', 'declared_customer_status',
    ],

    # ─── مرکز مشتریان: پذیرش و پرونده ───
    'customers.Reception': [
        'person_type', 'has_visit', 'wait_choice',
        'wait_minutes_total', 'is_waiting', 'info_submitted',
    ],
    'customers.CustomerCase': [
        'condition', 'cheque_owner', 'cheque_other_name', 'cheque_other_phone',
        'job', 'credit_rank', 'active_loans', 'product', 'quantity', 'visit_result',
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