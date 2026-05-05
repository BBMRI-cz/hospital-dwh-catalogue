from __future__ import annotations

from django import template
from django.http import QueryDict
from django.utils.translation import gettext

from frontend.presentation.filters import FilterState
from frontend.presentation.types import FrontendFilterChip

register = template.Library()

_DEFAULT_CHIP_CLASS = (
    'inline-flex max-w-full items-start gap-1 rounded-md border border-mmci-cyan-border '
    'bg-white px-2.5 py-1 text-xs font-medium text-mmci-blue shadow-sm'
)
_KEYWORD_CHIP_CLASS = (
    'inline-flex max-w-full items-center gap-1 rounded-full border border-mmci-cyan-border '
    'bg-mmci-cyan-light px-2.5 py-0.5 text-xs font-medium text-mmci-blue'
)


def _chip_values(filter_params: FilterState, key: str) -> list[str]:
    if key == 'q':
        value = filter_params.q
        return [value] if isinstance(value, str) and value else []
    if key == 'column':
        return sorted(item for item in filter_params.column if item)
    return sorted(item for item in filter_params.values_for(key) if item)


def _chip_label(filter_params: FilterState, key: str) -> str:
    if key == 'q':
        return gettext('Search')
    if key == 'column':
        return gettext('Column')
    return filter_params.filter_labels.get(key, key.replace('_', ' ').title())


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
    filter_keys = ('q', *filter_params.filter_order, 'column')
    for key in filter_keys:
        label = _chip_label(filter_params, key)
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
