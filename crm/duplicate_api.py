"""Real-time duplicate check API."""
from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET

from .duplicate_check import find_exact_match


_DETAIL_URLS = {
    "customer": "customers:detail",
    "employee": "hr:employee_detail",
    "product": "products:detail",
    "ad": "ads:edit",
}

_LIST_URLS = {
    "category": "products:category_list",
    "adplatform": "ads:platform_list",
    "adsource": "ads:source_list",
}

_MODEL_MAP = {
    "customer": "customers.Customer",
    "employee": "hr.Employee",
    "product": "products.Product",
    "category": "products.Category",
    "user": "auth.User",
    "ad": "ads.Ad",
    "adplatform": "ads.AdPlatform",
    "adsource": "ads.AdSource",
    "invoice": "sales.Invoice",
    "call": "calls.Call",
}

_FIELD_MAP = {
    "mobile": ("phone", "شماره تماس"),
    "phone_number": ("phone_number", "شماره تماس"),
    "national_id": ("national_id", "کد ملی"),
    "code": ("code", "کد کالا"),
    "slug": ("slug", "نام کوتاه"),
    "username": ("username", "نام کاربری"),
    "email": ("email", "ایمیل"),
    "ad_number": ("ad_number", "شناسه آگهی"),
    "name": ("name", "نام"),
}


def _normalizers():
    from .duplicate_check import (
        normalize_code, normalize_digits, normalize_email,
        normalize_phone, normalize_text,
    )
    return {
        "code": normalize_code,
        "slug": normalize_code,
        "username": normalize_code,
        "ad_number": normalize_code,
        "phone": normalize_phone,
        "phone_number": normalize_phone,
        "national_id": normalize_digits,
        "email": normalize_email,
        "text": normalize_text,
        "name": normalize_text,
    }


def _resolve(model_name):
    ref = _MODEL_MAP.get(model_name, model_name)
    if "." in ref:
        app_label, _, cls = ref.partition(".")
        return apps.get_model(app_label, cls)
    raise LookupError(model_name)


@login_required
@require_GET
def check_duplicate(request):
    model_name = request.GET.get("model", "").strip()
    field_name = request.GET.get("field", "").strip()
    value = request.GET.get("value", "").strip()
    exclude_pk = request.GET.get("exclude_pk", "").strip()

    if not model_name or not field_name:
        return JsonResponse({"error": "missing_params"}, status=400)

    try:
        Model = _resolve(model_name)
    except LookupError:
        return JsonResponse({"error": "unknown_model"}, status=400)

    try:
        Model._meta.get_field(field_name)
    except Exception:
        return JsonResponse({"error": "unknown_field"}, status=400)

    if not value:
        return JsonResponse({"exists": False})

    nkey, label = _FIELD_MAP.get(field_name, ("text", field_name))
    normalizer = _normalizers().get(nkey, lambda x: x)

    manager = getattr(Model, "all_objects", Model.objects)
    exclude = int(exclude_pk) if exclude_pk.isdigit() else None

    try:
        match = find_exact_match(
            Model, field_name, value, normalizer,
            exclude_pk=exclude, manager=manager,
        )
    except Exception as e:
        return JsonResponse({"error": f"internal:{e}"}, status=500)

    if not match:
        return JsonResponse({"exists": False})

    is_deleted = bool(getattr(match, "is_deleted", False))

    view_url = None
    if model_name in _DETAIL_URLS:
        try:
            view_url = reverse(_DETAIL_URLS[model_name], args=[match.pk])
        except Exception:
            pass
    elif model_name in _LIST_URLS:
        try:
            view_url = reverse(_LIST_URLS[model_name])
        except Exception:
            pass

    return JsonResponse({
        "exists": True,
        "field": field_name,
        "label": label,
        "display": str(match),
        "pk": match.pk,
        "is_deleted": is_deleted,
        "url": view_url,
    })
