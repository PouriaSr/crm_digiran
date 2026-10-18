from django.urls import path
from . import views

app_name = 'hr'

urlpatterns = [
    path('', views.employee_list, name='employee_list'),
    path('employees/new/', views.employee_create, name='employee_create'),
    path('employees/<int:pk>/', views.employee_detail, name='employee_detail'),
    path('employees/<int:pk>/edit/', views.employee_edit, name='employee_edit'),
    path('employees/<int:pk>/delete/', views.employee_delete, name='employee_delete'),

    path('tasks/', views.task_list, name='task_list'),
    path('tasks/new/', views.task_create, name='task_create'),
    path('tasks/<int:pk>/', views.task_detail, name='task_detail'),
    path('tasks/<int:pk>/edit/', views.task_edit, name='task_edit'),
    path('tasks/<int:pk>/delete/', views.task_delete, name='task_delete'),
    path('tasks/<int:pk>/toggle/', views.task_toggle_status, name='task_toggle'),

    path('leaves/', views.leave_list, name='leave_list'),
    path('leaves/new/', views.leave_create, name='leave_create'),
    path('leaves/<int:pk>/review/', views.leave_review, name='leave_review'),

    path('attendance/', views.attendance_list, name='attendance_list'),
    path('attendance/new/', views.attendance_create, name='attendance_create'),
    path('attendance/<int:pk>/edit/', views.attendance_edit, name='attendance_edit'),
    path('attendance/<int:pk>/delete/', views.attendance_delete, name='attendance_delete'),
    path('attendance/report/', views.attendance_report, name='attendance_report'),

    path('my-profile/', views.my_profile, name='my_profile'),
    path('my-profile/edit/', views.edit_my_profile, name='edit_my_profile'), # ⭐ مسیر جدید
]