from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from .structure_registry import scope_for_request,component_scopes
from .structure_service import schema,can_access


class StructureAccessMiddleware(MiddlewareMixin):
    def process_view(self,request,view_func,view_args,view_kwargs):
        if not getattr(request,'user',None) or not request.user.is_authenticated:return
        key=scope_for_request(request)
        if not key:return
        section=schema(key,request)
        if not section:return
        from .permissions import get_user_role,has_permission
        if not section.enabled or section.roles and get_user_role(request.user) not in section.roles or section.permission and not has_permission(request.user,section.permission):raise PermissionDenied('این بخش برای نقش شما فعال نیست.')
        if request.method=='GET':
            from .interface import component_settings,catalog
            dropped=[]
            for setting in component_settings(request):
                definition=catalog().get(setting.key,{})
                if not setting.enabled and key in component_scopes(setting.key,definition) and definition.get('filter_name'):dropped.append(definition['filter_name'])
            if dropped:
                request.GET=request.GET.copy()
                for name in dropped:request.GET.pop(name,None)
        if request.method=='POST' and section.gate_save and key=='info':
            from customers.models import Customer
            from .models import SectionRecord
            from django.contrib.contenttypes.models import ContentType
            subject=Customer.objects.filter(mobile=request.POST.get('mobile','')).first()
            from customers.access import can_edit_card
            if not subject or not has_permission(request.user,'calls.add') or not can_edit_card(request.user,subject):return
            record=SectionRecord.objects.filter(section=section,content_type=ContentType.objects.get_for_model(subject),object_id=subject.pk).select_related('stage').first()
            if not record or not record.stage_id or record.stage.status!='done':
                return JsonResponse({'error':'ابتدا مراحل تعریف‌شده این بخش را در «اطلاعات تکمیلی و مراحل» تکمیل کنید.'},status=409)
