from django import template

register = template.Library()


@register.filter
def is_list(value: object) -> bool:
    """Return True if *value* is a list (not a string)."""
    return isinstance(value, list)
