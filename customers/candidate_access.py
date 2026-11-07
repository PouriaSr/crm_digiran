"""Keep recruitment records out of sales actions, including direct POSTs."""
from django.http import HttpResponseForbidden
from django.utils.deprecation import MiddlewareMixin
from .models import Customer


class CandidateWorkflowMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if not match or not request.user.is_authenticated:
            return
        app, name = match.app_name, match.url_name or ''
        person = None
        if app == 'customers':
            if name in {'edit','reassign','deactivate','restore','note_create','note_edit','note_delete','note_toggle_pin','quick_call'}:
                person = Customer.all_objects.filter(pk=view_kwargs.get('pk'),is_interviewer=True).first()
            elif name == 'hub_submit_call' and str(request.POST.get('is_interviewer','')).lower() in ('','false'):
                from crm.numerals import normalize_input
                person = Customer.all_objects.filter(mobile=normalize_input(request.POST.get('mobile','')),is_interviewer=True).first()
            elif name in {'hub_call_edit','hub_followup_done'}:
                from calls.models import Call
                person = Call.objects.filter(pk=view_kwargs.get('pk'),customer__is_interviewer=True).first()
        elif app in {'calls','sales'} or (app == 'admin' and request.method == 'POST' and name.startswith(('calls_call_','sales_invoice_'))):
            if app == 'admin':
                app = 'calls' if name.startswith('calls_call_') else 'sales'
                identifier = str(view_kwargs.get('object_id',''))
                if identifier.isascii() and identifier.isdigit():
                    if app == 'calls':
                        from calls.models import Call
                        person=Call.objects.filter(pk=identifier,customer__is_interviewer=True).first()
                    else:
                        from sales.models import Invoice
                        person=Invoice.objects.filter(pk=identifier,customer__is_interviewer=True).first()
            if name not in {'list','create','new'} and view_kwargs.get('pk'):
                if app == 'calls':
                    from calls.models import Call
                    person = Call.objects.filter(pk=view_kwargs['pk'],customer__is_interviewer=True).first()
                else:
                    from sales.models import Invoice
                    person = Invoice.objects.filter(pk=view_kwargs['pk'],customer__is_interviewer=True).first()
            if request.method == 'POST':
                identifier = request.POST.get('customer','')
                if identifier.isascii() and identifier.isdigit():
                    person = Customer.all_objects.filter(pk=identifier,is_interviewer=True).first() or person
                from crm.numerals import normalize_input
                phone = normalize_input(request.POST.get('call_number',''))
                if phone:
                    person = Customer.all_objects.filter(mobile=phone,is_interviewer=True).first() or person
        if person:
            return HttpResponseForbidden('این فرد مصاحبه‌کننده است؛ عملیات مشتری برای او مجاز نیست. از پرونده استخدام استفاده کنید.')
