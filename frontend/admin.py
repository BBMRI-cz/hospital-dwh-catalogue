"""Admin configuration for frontend-owned catalogue settings."""

from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from frontend.models import CatalogueFilterDefinition
from frontend.presentation.filters import get_supported_filter_field_choices


class CatalogueFilterDefinitionForm(forms.ModelForm):
    class Meta:
        model = CatalogueFilterDefinition
        fields = ['field_name', 'label', 'sort_order', 'is_enabled']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = list(get_supported_filter_field_choices())
        current_value = self.instance.field_name if self.instance and self.instance.pk else ''
        if current_value and current_value not in {value for value, _label in choices}:
            choices.append(
                (current_value, _('%(field)s (currently unavailable)') % {'field': current_value})
            )
        self.fields['field_name'] = forms.ChoiceField(
            choices=choices,
            label=_('Field name'),
            help_text=_(
                'Only dataset metadata fields mapped into the unified catalogue model are available.'
            ),
        )


@admin.register(CatalogueFilterDefinition)
class CatalogueFilterDefinitionAdmin(admin.ModelAdmin):
    form = CatalogueFilterDefinitionForm
    list_display = ('label', 'field_name', 'sort_order', 'is_enabled')
    list_editable = ('sort_order', 'is_enabled')
    list_filter = ('is_enabled',)
    search_fields = ('label', 'field_name')
    ordering = ('sort_order', 'label', 'field_name')
