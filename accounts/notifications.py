from django.utils import timezone
from accounts.permissions import has_permission

def get_notifications(user):
    """تولید اعلان‌های پویا برای کاربر بر اساس دسترسی‌ها و وضعیت سیستم"""
    if not user.is_authenticated:
        return []

    notifications = []
    today = timezone.now().date()

    # ۱. هشدار وظایف عقب‌افتاده
    if has_permission(user, 'hr.view_tasks'):
        from hr.models import Task
        overdue_tasks = Task.objects.filter(due_date__lt=today).exclude(status__in=['done', 'cancelled'])
        
        # اگر کاربر مدیر کل نیست، فقط وظایف خودش را ببیند
        if not user.is_superuser and not has_permission(user, 'hr.manage_tasks'):
            overdue_tasks = overdue_tasks.filter(assigned_to__user=user)
            
        count = overdue_tasks.count()
        if count > 0:
            notifications.append({
                'icon': '⚠️',
                'title': f'شما {count} وظیفه عقب‌افتاده دارید.',
                'url': '/hr/tasks/?due=overdue', # ⭐ لینک اصلاح شد
                'color': 'text-orange-600',
                'bg': 'bg-orange-50'
            })

    # ۲. درخواست‌های مرخصی در انتظار (فقط برای مدیران)
    if has_permission(user, 'hr.review_leaves'):
        from hr.models import LeaveRequest
        pending_leaves = LeaveRequest.objects.filter(status='pending').count()
        if pending_leaves > 0:
            notifications.append({
                'icon': '🏖',
                'title': f'{pending_leaves} درخواست مرخصی در انتظار بررسی است.',
                'url': '/hr/leaves/?status=pending',
                'color': 'text-blue-600',
                'bg': 'bg-blue-50'
            })

    # ۳. مشتریان نیازمند پیگیری
    if has_permission(user, 'customers.view'):
        from customers.models import Customer
        # در سیستم جدید «نیاز به پیگیری» یک پرچم روی مشتری است (تاریخ جمع نمی‌شود)
        followups = Customer.objects.filter(needs_followup=True)

        if not user.is_superuser:
            followups = followups.filter(assigned_to=user)
            
        count_followups = followups.count()
        if count_followups > 0:
            notifications.append({
                'icon': '📞',
                'title': f'{count_followups} تماس نیازمند پیگیری دارید.',
                'url': '/customers/hub/?tab=info',   # لیست مشتریان (تب تماس و پیگیری حذف شد)
                'color': 'text-green-600',
                'bg': 'bg-green-50'
            })

    return notifications