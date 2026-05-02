"""Frontend-owned configuration models."""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

RESERVED_FILTER_FIELD_NAMES = frozenset({'q', 'page', 'status', 'column'})


class CatalogueFilterDefinition(models.Model):
    """Staff-configurable dataset metadata filter shown in the catalogue sidebar."""

    field_name = models.SlugField(
        max_length=80,
        unique=True,
        verbose_name=_('Field name'),
        help_text=_('Dataset metadata field used as the catalogue query parameter.'),
    )
    label = models.CharField(
        max_length=120,
        verbose_name=_('Label'),
        help_text=_('Human-readable filter group title shown in the sidebar.'),
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Sort order'),
        help_text=_('Lower numbers are shown first.'),
    )
    is_enabled = models.BooleanField(
        default=True,
        verbose_name=_('Enabled'),
    )

    class Meta:
        db_table = 'frontend_catalogue_filter_definition'
        verbose_name = _('Catalogue Filter Definition')
        verbose_name_plural = _('Catalogue Filter Definitions')
        ordering = ['sort_order', 'label', 'field_name']

    def __str__(self) -> str:
        return f'{self.label} ({self.field_name})'

    def clean(self) -> None:
        super().clean()
        if self.field_name in RESERVED_FILTER_FIELD_NAMES:
            raise ValidationError(
                {
                    'field_name': _('%(field_name)s is reserved for built-in catalogue parameters.')
                    % {'field_name': self.field_name}
                }
            )
