from django import forms


class SourceSelect(forms.Select):
    """Shared source search metadata and label-first text throughout the system."""

    def __init__(self, attrs=None, choices=()):
        super().__init__({'data-source-search': 'label-first', **(attrs or {})}, choices)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        source = getattr(value, 'instance', None)
        if source is not None:
            option['attrs']['data-source-label'] = source.label
            option['attrs']['data-source-number'] = source.phone_number
            option['label'] = f'{source.label} — {source.phone_number}' if source.label else source.phone_number
        return option


# Keep existing call forms using the same shared widget.
ContactSourceSelect = SourceSelect
