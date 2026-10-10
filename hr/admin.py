from django.contrib import admin
from .models import Employee, Task, LeaveRequest, Attendance


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'position', 'mobile', 'hire_date', 'is_active')
    list_filter = ('position', 'contract_type', 'is_active')
    search_fields = ('first_name', 'last_name', 'mobile', 'national_id')
    ordering = ('-created_at',)

    fieldsets = (
        ('اطلاعات شخصی', {
            'fields': ('user', 'first_name', 'last_name', 'national_id', 'mobile', 'email', 'address', 'birth_date')
        }),
        ('اطلاعات شغلی', {
            'fields': ('position', 'contract_type', 'hire_date', 'salary', 'is_active')
        }),
        ('توضیحات', {
            'fields': ('notes',)
        }),
    )


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'assigned_to', 'priority', 'status', 'due_date', 'is_overdue')
    list_filter = ('priority', 'status', 'assigned_to')
    search_fields = ('title', 'description')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    autocomplete_fields = ['assigned_to']

    def is_overdue(self, obj):
        return obj.is_overdue
    is_overdue.boolean = True
    is_overdue.short_description = 'عقب‌افتاده؟'


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'start_date', 'end_date', 'days_count', 'status', 'created_at')
    list_filter = ('leave_type', 'status', 'created_at')
    search_fields = ('employee__first_name', 'employee__last_name', 'reason')
    date_hierarchy = 'start_date'
    ordering = ('-created_at',)
    autocomplete_fields = ['employee']
    readonly_fields = ('days_count', 'created_at', 'updated_at', 'reviewed_at')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'check_in', 'check_out', 'work_hours_display', 'status')
    list_filter = ('status', 'date', 'employee')
    search_fields = ('employee__first_name', 'employee__last_name')
    date_hierarchy = 'date'
    ordering = ('-date',)
    autocomplete_fields = ['employee']

    def work_hours_display(self, obj):
        return obj.work_hours_display
    work_hours_display.short_description = 'ساعت کاری'