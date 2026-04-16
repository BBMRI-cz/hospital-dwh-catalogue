from __future__ import annotations

from django import template
from django.http import QueryDict
from django.utils.translation import gettext

from frontend.presentation.filters import FilterState
from frontend.presentation.types import FrontendFilterChip

register = template.Library()

_FILTER_LABELS: tuple[tuple[str, str], ...] = (
    ('q', gettext('Search')),
    ('keywords', gettext('Keyword')),
    ('custodian', gettext('Custodian')),
    ('health_category', gettext('Health Category')),
    ('source', gettext('Source')),
    ('theme', gettext('Theme')),
    ('column', gettext('Column')),
)

_DEFAULT_CHIP_CLASS = (
    'inline-flex max-w-full items-start gap-1 rounded-md border border-mou-cyan-border '
    'bg-white px-2.5 py-1 text-xs font-medium text-mou-blue shadow-sm'
)
_KEYWORD_CHIP_CLASS = (
    'inline-flex max-w-full items-center gap-1 rounded-full border border-mou-cyan-border '
    'bg-mou-cyan-light px-2.5 py-0.5 text-xs font-medium text-mou-blue'
)


def _chip_values(filter_params: FilterState, key: str) -> list[str]:
    value = getattr(filter_params, key, None)
    if key == 'q':
        return [value] if isinstance(value, str) and value else []
    if isinstance(value, set):
        return sorted(item for item in value if item)
    return []


def _build_remove_url(base_url: str, query_params: QueryDict, key: str, value: str) -> str:
    updated_params = query_params.copy()
    if key == 'q':
        updated_params.pop(key, None)
    else:
        remaining_values = [item for item in updated_params.getlist(key) if item != value]
        if remaining_values:
            updated_params.setlist(key, remaining_values)
        else:
            updated_params.pop(key, None)
    updated_params.pop('page', None)
    updated_params['page'] = '1'
    return f'{base_url}?{updated_params.urlencode()}'


@register.simple_tag
def active_filter_chips(
    filter_params: FilterState,
    query_params: QueryDict,
    base_url: str,
) -> list[FrontendFilterChip]:
    """Return the rendered active-filter chip data for the catalogue results partial."""
    chips: list[FrontendFilterChip] = []
    for key, label in _FILTER_LABELS:
        for value in _chip_values(filter_params, key):
            chips.append(
                FrontendFilterChip(
                    display=f'{label}: {value}',
                    title=f'{label}: {value}',
                    remove_url=_build_remove_url(base_url, query_params, key, value),
                    container_class=(
                        _KEYWORD_CHIP_CLASS if key == 'keywords' else _DEFAULT_CHIP_CLASS
                    ),
                )
            )
    return chips


@register.filter
def is_list(value: object) -> bool:
    """Return True if *value* is a list (not a string)."""
    return isinstance(value, list)
