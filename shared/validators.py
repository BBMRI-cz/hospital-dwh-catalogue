"""
Shared field-level validators for HealthDCAT-AP mandatory fields.

Validators here are model-agnostic: they receive any object and a list
of field names to check.  They are called from the clean() method of the
abstract base models so the logic never has to be duplicated.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_mandatory_fields(obj: object, fields: list[str]) -> None:
    """
    Raise a field-keyed ValidationError for every field in *fields* that
    is blank (empty string) or None on *obj*.

    Args:
        obj:    Model instance being validated.
        fields: List of attribute names that must be non-blank / non-None.

    Raises:
        ValidationError: Dict of {field_name: [error_message]} for all
                         failing fields.  Raised only when at least one
                         field fails so that the caller receives all
                         failures at once.
    """
    errors: dict[str, list] = {}
    for field_name in fields:
        value = getattr(obj, field_name, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors[field_name] = [
                _('%(field)s is mandatory (HealthDCAT-AP v6).') % {'field': field_name}
            ]
    if errors:
        raise ValidationError(errors)
