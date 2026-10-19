"""
Mixin برای چک تکراری لحظه‌ای (Real-time) در فرم‌ها.
"""


class DuplicateCheckMixin:
    duplicate_model = None
    duplicate_fields = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.duplicate_model:
            return

        exclude_pk = ""
        instance = getattr(self, "instance", None)
        if instance and getattr(instance, "pk", None):
            exclude_pk = str(instance.pk)

        for field_name in self.duplicate_fields:
            if field_name not in self.fields:
                continue
            widget = self.fields[field_name].widget
            widget.attrs["data-check-duplicate"] = "1"
            widget.attrs["data-duplicate-model"] = self.duplicate_model
            widget.attrs["data-duplicate-field"] = field_name
            if exclude_pk:
                widget.attrs["data-exclude-pk"] = exclude_pk
