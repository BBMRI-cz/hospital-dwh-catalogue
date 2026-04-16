"""Shared validators for HealthDCAT-AP models."""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_mandatory_fields(obj: object, fields: list[str]) -> None:
    """Raise a field-keyed error for every blank or missing mandatory field."""
    errors: dict[str, list] = {}
    for field_name in fields:
        value = getattr(obj, field_name, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors[field_name] = [
                _('%(field)s is mandatory (HealthDCAT-AP v6).') % {'field': field_name}
            ]
    if errors:
        raise ValidationError(errors)
