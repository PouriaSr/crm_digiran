"""Trusted bindings between editable sections and existing models/views."""
SECTIONS = {
 'info': {'label':'اطلاعات','model':'customers.Customer','read':'customers.info','write':'calls.add','path':'/customers/hub/','tab':'info','forms':['customers.forms.CustomerForm','customers.forms.HubCallForm'],'fields':['name','mobile','source','stage','assigned_to','created_at','email','address','notes']},
 'reception': {'label':'پذیرش','model':'customers.Reception','read':'customers.reception','write':'customers.reception_add','path':'/customers/hub/','tab':'reception','forms':[],'fields':['customer__name','customer__mobile','person_type','arrived_at','referred_at','created_at']},
 'case': {'label':'پرونده','model':'customers.CustomerCase','read':'customers.case','write':'customers.case_edit','path':'/customers/hub/','tab':'case','forms':['customers.forms.CustomerCaseForm'],'fields':['customer__name','customer__mobile','condition','job','credit_rank','quantity','visit_result']},
 'registration': {'label':'ثبت اطلاعات','model':'customers.Customer','read':'customers.registration','write':'customers.registration_edit','path':'/customers/hub/','tab':'registration','forms':['customers.forms.CustomerForm'],'fields':['name','mobile','email','address','source','stage','created_at']},
 'hiring': {'label':'استخدام','model':'customers.HiringApplication','read':'customers.hiring','write':'customers.hiring_interview','path':'/customers/hub/','tab':'hiring','forms':['customers.hiring_forms.InterviewForm'],'fields':['reception__customer__name','reception__customer__mobile','status','current_arrived_at']},
 'products': {'label':'کالاها','model':'products.Product','read':'products.view','write':'products.edit','path':'/products/','forms':['products.forms.ProductForm'],'fields':['name','code','price','cost_price','stock','min_stock','is_active']},
 'categories': {'label':'گروه کالا','model':'products.Category','read':'categories.view','write':'categories.manage','path':'/products/categories/','forms':['products.forms.CategoryForm'],'fields':['name','slug','is_active']},
 'calls': {'label':'تماس‌ها','model':'calls.Call','read':'calls.view','write':'calls.edit','path':'/calls/','forms':['calls.forms.CallForm'],'fields':['caller_name','call_number','contact_type','status','notes','call_date','follow_up_date']},
 'invoices': {'label':'فاکتورها','model':'sales.Invoice','read':'invoices.view','write':'invoices.edit','path':'/invoices/','forms':['sales.forms.InvoiceForm'],'fields':['number','customer__name','status','total','created_at']},
 'employees': {'label':'پرسنل','model':'hr.Employee','read':'hr.view_employees','write':'hr.manage_employees','path':'/hr/','forms':['hr.forms.EmployeeForm'],'fields':['first_name','last_name','mobile','position','is_active']},
 'tasks': {'label':'وظایف','model':'hr.Task','read':'hr.view_tasks','write':'hr.manage_tasks','path':'/hr/tasks/','forms':['hr.forms.TaskForm'],'fields':['title','status','priority','due_date','due_time','created_at']},
 'leaves': {'label':'مرخصی','model':'hr.LeaveRequest','read':'hr.review_leaves','write':'hr.review_leaves','path':'/hr/leaves/','forms':['hr.forms.LeaveRequestForm'],'fields':['employee__first_name','employee__last_name','status','leave_type','start_date','end_date']},
 'attendance': {'label':'حضور و غیاب','model':'hr.Attendance','read':'hr.attendance','write':'hr.attendance','path':'/hr/attendance/','forms':['hr.forms.AttendanceForm'],'fields':['employee__first_name','employee__last_name','date']},
 'ads': {'label':'تبلیغات','model':'ads.Ad','read':'ads.view','write':'ads.edit','path':'/ads/','forms':['ads.forms.AdForm'],'fields':['ad_number','cost','note','created_at']},
 'ad_sources': {'label':'منابع تبلیغ','model':'ads.AdSource','read':'ads.manage_defs','write':'ads.manage_defs','path':'/ads/manage/sources/','forms':['ads.forms.AdSourceForm'],'fields':['label','phone_number','is_active']},
}
SECTIONS.update({
 'users': {'label':'کاربران سیستم','model':'auth.User','read':'accounts.manage_users','write':'accounts.manage_users','path':'/accounts/users/','forms':['accounts.forms.UserCreateForm','accounts.forms.UserEditForm'],'fields':['username','first_name','last_name','email','is_active']},
 'ad_platforms': {'label':'عناوین تبلیغات','model':'ads.AdPlatform','read':'ads.manage_defs','write':'ads.manage_defs','path':'/ads/manage/platforms/','forms':['ads.forms.AdPlatformForm'],'fields':['name','is_active']},
 'ad_processes': {'label':'فرآیندهای تبلیغ','model':'ads.AdProcess','read':'ads.manage_defs','write':'ads.manage_defs','path':'/ads/manage/processes/','forms':['ads.forms.AdProcessForm'],'fields':['name','platform__name','default_cost','is_active']},
})

# Lists may show visits while the configurable data belongs to the dossier/person.
LIST_BINDINGS={'case':('customers.Reception','customer__case'), 'registration':('customers.Reception','customer'), 'hiring':('customers.Reception','hiring')}


def scope_for_request(request):
    explicit=getattr(request,'_structure_scope',None)
    if explicit:return explicit
    match=getattr(request,'resolver_match',None)
    name=match.view_name if match else ''
    if name in ('customers:hub','customers:hub_submit_call'):
        if name.endswith(':hub'):
            from customers.reception_workflow import allowed_tabs
            tab=getattr(request,'_hub_tab',None) or request.GET.get('tab') or next(iter(allowed_tabs(request.user)),None)
            tab={'call':'info','followup':'info','visit':'info','recruitment':'hiring'}.get(tab,tab)
            return 'invoices' if tab=='invoice' else tab
        return 'info'
    if name in ('customers:detail','customers:edit','customers:create','customers:form_modal'):return 'info'
    if name=='customers:registration_form':return 'registration'
    if name=='customers:case_save':return 'case'
    if name=='customers:reception_action':return 'reception'
    for key,definition in sorted(SECTIONS.items(),key=lambda item:-len(item[1]['path'])):
        if definition['path']!='/customers/hub/' and request.path_info.startswith(definition['path']):return key
    return None


def component_scopes(key, definition):
    if key.startswith('hub.tab.'):return ['invoices' if key.split('.')[-1]=='invoice' else key.split('.')[-1]]
    if definition.get('scopes'):return definition['scopes']
    path=definition.get('path','')
    for scope in ('reception','case','registration','hiring'):
        if scope in path:return [scope]
    if '_workflow' in path:return ['reception','case','registration','hiring']
    if path.startswith('customers/_interview') or path in ('customers/_recruitment_tab.html','customers/candidate_detail.html'):return ['hiring']
    if path.startswith('customers/_invoice'):return ['invoices']
    if path.startswith('customers/_admission'):return ['info','reception']
    if path in ('customers/_candidate_actions.html','customers/_candidate_identity.html','customers/_candidate_filters.html'):return ['info','hiring']
    if path.endswith('_customer_fields.html'):return ['info','registration']
    if path.startswith('customers/'):
        return ['info']
    if key.startswith('field.'):
        form=key[6:].rsplit('.',1)[0]
        return [scope for scope,entry in SECTIONS.items() if form in entry['forms']]
    if path.startswith('products/'):return ['categories' if 'categor' in path else 'products']
    if path.startswith('hr/'):
        for needle,scope in [('task','tasks'),('leave','leaves'),('attendance','attendance'),('employee','employees'),('profile','employees')]:
            if needle in path:return [scope]
    if path.startswith('ads/'):
        for needle,scope in [('source','ad_sources'),('platform','ad_platforms'),('process','ad_processes')]:
            if needle in path:return [scope]
        return ['ads']
    if path.startswith('accounts/user'):return ['users']
    if '_workflow' in path:return ['reception','case','registration','hiring']
    prefix=path.split('/')[0]
    return {'products':['products','categories'],'calls':['calls'],'sales':['invoices'],'hr':['employees','tasks','leaves','attendance'],'ads':['ads','ad_sources']}.get(prefix,[])

# Only these templates contain the corresponding data-entry form. A list/filter
# button cannot open a selector belonging to an unrelated record form.
FORM_TEMPLATES = {
 'customers/_call_modal.html':['customers.forms.HubCallForm'],
 'customers/_customer_fields.html':['customers.forms.CustomerForm'],
 'customers/form.html':['customers.forms.CustomerForm'],
 'customers/form_modal.html':['customers.forms.CustomerForm'],
 'customers/_case_tab.html':['customers.forms.CustomerCaseForm'],
 'customers/_interview_modal.html':['customers.hiring_forms.InterviewForm'],
 'products/form.html':['products.forms.ProductForm'],
 'products/category_form.html':['products.forms.CategoryForm'],
 'calls/form.html':['calls.forms.CallForm'],
 'sales/form.html':['sales.forms.InvoiceForm'],
 'hr/employee_form.html':['hr.forms.EmployeeForm'],
 'hr/task_form.html':['hr.forms.TaskForm'],
 'hr/leave_form.html':['hr.forms.LeaveRequestForm'],
 'hr/attendance_form.html':['hr.forms.AttendanceForm'],
 'ads/ad_form.html':['ads.forms.AdForm'],
 'accounts/user_form.html':['accounts.forms.UserCreateForm','accounts.forms.UserEditForm'],
}
