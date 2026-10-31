from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import path

from accounts.permissions import require_permission
from . import views, hub_views, reception_workflow, hiring_views

app_name = 'customers'


@login_required
@require_permission('customers.view')
def to_hub(request):
    return redirect('/customers/hub/?tab=info')


urlpatterns = [
    # Redirect old list to new Hub
    path('', to_hub, name='list'),
    
    # New Hub Routes
    path('hub/', hub_views.customer_hub, name='hub'),
    path('hub/call/', hub_views.hub_submit_call, name='hub_submit_call'),
    path('hub/api/check/', hub_views.hub_check_customer, name='hub_check_api'),
    path('hub/followup/<int:pk>/done/', hub_views.hub_followup_done, name='hub_followup_done'),

    # Original CRUD Routes (Crucial for detail.html and forms to work)
    path('new/', views.customer_create, name='create'),
    path('<int:pk>/', views.customer_detail, name='detail'),
    path('<int:pk>/edit/', views.customer_edit, name='edit'),
    path('hub/case/save/', hub_views.hub_case_save, name='case_save'),
    path('hub/case/<int:pk>/open/', reception_workflow.case_open, name='case_open'),
    path('hub/case/clock/', reception_workflow.case_clock, name='case_clock'),
    path('hub/hiring/sessions/clock/', hiring_views.interview_clock, name='interview_clock'),
    path('hub/hiring/<int:pk>/interview/open/', hiring_views.interview_open, name='interview_open'),
    path('hub/hiring/session/<int:pk>/end/', hiring_views.interview_end, name='interview_end'),
    path('hub/hiring/session/<int:pk>/save/', hiring_views.interview_save, name='interview_save'),
    path('hub/hiring/session/<int:pk>/edit/', hiring_views.interview_edit, name='interview_edit'),
    path('hub/hiring/<int:pk>/identity/', hiring_views.hiring_identity, name='hiring_identity'),
    path('hub/hiring/<int:pk>/resume/', hiring_views.hiring_resume, name='hiring_resume'),
    path('hub/hiring/<int:pk>/resume/upload/', hiring_views.hiring_resume_upload, name='hiring_resume_upload'),
    path('hub/hiring/<int:pk>/refer/', hiring_views.hiring_refer, name='hiring_refer'),
    path('hub/hiring/ads/new/', hiring_views.hiring_ad_create, name='hiring_ad_create'),
    path('hub/reception/clock/', reception_workflow.reception_clock, name='reception_clock'),
    path('hub/hiring/clock/', reception_workflow.hiring_clock, name='hiring_clock'),
    path('hub/registration/<int:pk>/', reception_workflow.registration_form, name='registration_form'),
    path('hub/reception/action/', hub_views.hub_reception_action, name='reception_action'),
    path('<int:pk>/quick-call/', hub_views.hub_quick_call, name='quick_call'),
    path('hub/calls/<int:pk>/edit/', hub_views.hub_call_edit, name='hub_call_edit'),
    path('<int:pk>/reassign/', hub_views.customer_reassign, name='reassign'),
    path('<int:pk>/deactivate/', views.customer_deactivate, name='deactivate'),
    path('<int:pk>/restore/', views.customer_restore, name='restore'),
    path('inactive/', views.customer_inactive_list, name='inactive_list'),

    # Notes
    path('<int:pk>/notes/add/', views.note_create, name='note_create'),
    path('<int:pk>/notes/<int:note_pk>/edit/', views.note_edit, name='note_edit'),
    path('<int:pk>/notes/<int:note_pk>/delete/', views.note_delete, name='note_delete'),
    path('<int:pk>/notes/<int:note_pk>/pin/', views.note_toggle_pin, name='note_toggle_pin'),

    # Excel
    path('excel/', views.customer_excel_import, name='excel_import'),
    path('excel/template/', views.customer_excel_template, name='excel_template'),
    path('excel/<uuid:token>/', views.customer_excel_preview, name='excel_preview'),
]
