from django.utils import timezone
from django.urls import reverse
from accounts.permissions import has_permission

def get_notifications(user):
    """تولید اعلان‌های پویا برای کاربر بر اساس دسترسی‌ها و وضعیت سیستم"""
    if not user.is_authenticated:
        return []

    notifications = []
    today = timezone.now().date()

    # ۱. هشدار وظایف عقب‌افتاده
    if has_permission(user, 'hr.view_tasks'):
        from hr.task_access import visible_tasks, overdue_condition
        overdue_tasks = visible_tasks(user).filter(overdue_condition())

        from hr.task_inbox import inbox_records, inbox_counts
        records, own, events, notices = inbox_records(user)
        counts = inbox_counts(records, own, events, notices)
        if counts['attention'] or counts['updates_unread']:
            title = (f"{counts['attention']} کار نیاز به رسیدگی شما دارد." if counts['attention'] else f"{counts['updates_unread']} تغییر خوانده‌نشده در وظایف شما ثبت شده است.")
            notifications.append({'icon':'📋','title':title, 'url':reverse('hr:task_list')+'?scope=mine', 'color':'text-blue-600','bg':'bg-blue-50'})
        overdue_tasks = own.filter(overdue_condition())
        count = overdue_tasks.count()
        if count > 0:
            notifications.append({
                'icon': '⚠️',
                'title': f'شما {count} وظیفه عقب‌افتاده دارید.',
                'url': reverse('hr:task_list')+'?due=overdue', # ⭐ لینک اصلاح شد
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
        followups = Customer.objects.filter(needs_followup=True,is_interviewer=False)

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
