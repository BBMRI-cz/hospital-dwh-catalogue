"""Filtering and sidebar builders for the catalogue presentation layer."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from frontend.presentation.types import (
    FrontendDataset,
    FrontendSidebarContext,
    FrontendSidebarCounts,
    FrontendSidebarItem,
)
from shared.services import UnifiedCatalogService

_ALL_STATUSES = {'ready', 'raw', 'unavailable'}


@dataclass(slots=True)
class FilterState:
    q: str
    status: set[str]
    keywords: set[str]
    source: set[str]
    custodian: set[str]
    health_category: set[str]
    theme: set[str]
    column: set[str]

    @classmethod
    def from_query_params(cls, query_params) -> FilterState:
        return cls(
            q=query_params.get('q', ''),
            status=set(query_params.getlist('status')),
            keywords=set(query_params.getlist('keywords')),
            source=set(query_params.getlist('source')),
            custodian=set(query_params.getlist('custodian')),
            health_category=set(query_params.getlist('health_category')),
            theme=set(query_params.getlist('theme')),
            column=set(query_params.getlist('column')),
        )


def filter_datasets(
    datasets: list[FrontendDataset],
    filter_state: FilterState,
    *,
    service: UnifiedCatalogService | None = None,
) -> list[FrontendDataset]:
    keyword_filter = {keyword.lower() for keyword in filter_state.keywords}
    status_filter = filter_state.status or _ALL_STATUSES

    matching_dataset_names: frozenset[str] | None = None
    if filter_state.column:
        catalog_service = service or UnifiedCatalogService()
        matching_dataset_names = catalog_service.get_dataset_names_by_columns(filter_state.column)

    query = filter_state.q.strip().lower()
    result: list[FrontendDataset] = []
    for dataset in datasets:
        if dataset.status not in status_filter:
            continue
        if filter_state.source and dataset.source not in filter_state.source:
            continue
        if keyword_filter:
            dataset_keywords = {keyword.lower() for keyword in dataset.keywords}
            if not keyword_filter.intersection(dataset_keywords):
                continue
        if filter_state.custodian and dataset.custodian not in filter_state.custodian:
            continue
        if filter_state.health_category and not (
            set(dataset.health_category) & filter_state.health_category
        ):
            continue
        if filter_state.theme and not (set(dataset.theme) & filter_state.theme):
            continue
        if matching_dataset_names is not None and dataset.name not in matching_dataset_names:
            continue
        if query and query not in dataset.search_text:
            continue
        result.append(dataset)

    return result


def _agent_label(name: str) -> str:
    label = re.sub(r'AGENT_', '', name, flags=re.IGNORECASE)
    return label.replace('_', ' ').strip() or name


def _health_category_label(value: str) -> str:
    return value.replace('_', ' ').capitalize()


def _theme_label(value: str) -> str:
    parts = value.rstrip('/').rsplit('/', 2)
    if len(parts) >= 3:
        return f'{parts[-2]} / {parts[-1]}'
    return parts[-1] or value


def _build_distribution_index(
    datasets: list[FrontendDataset],
    table_column_apps: set[str],
) -> tuple[list[str], dict[str, str]]:
    distribution_names: list[str] = []
    distribution_to_dataset: dict[str, str] = {}

    for dataset in datasets:
        if dataset.app not in table_column_apps:
            continue
        for distribution in dataset.distributions:
            distribution_names.append(distribution.name)
            distribution_to_dataset[distribution.name] = dataset.name

    return distribution_names, distribution_to_dataset


def _make_sidebar_items(
    counter: Counter[str],
    active: set[str],
    label_fn: Callable[[str], str] | None = None,
) -> list[FrontendSidebarItem]:
    all_values = (set(counter) | active) - {''}
    items: list[FrontendSidebarItem] = []
    for value in sorted(all_values, key=lambda item: (item not in active, item.lower())):
        items.append(
            FrontendSidebarItem(
                value=value,
                label=label_fn(value) if label_fn else value,
                count=counter.get(value, 0),
                checked=value in active,
            )
        )
    return items


def build_sidebar_context(
    filtered: list[FrontendDataset],
    *,
    filter_state: FilterState,
    service: UnifiedCatalogService | None = None,
) -> FrontendSidebarContext:
    keyword_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()
    custodian_counter: Counter[str] = Counter()
    health_category_counter: Counter[str] = Counter()
    theme_counter: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()

    for dataset in filtered:
        for keyword in dataset.keywords:
            if keyword:
                keyword_counter[keyword] += 1
        if dataset.source:
            source_counter[dataset.source] += 1
        if dataset.custodian:
            custodian_counter[dataset.custodian] += 1
        for health_category in dataset.health_category:
            if health_category:
                health_category_counter[health_category] += 1
        for theme in dataset.theme:
            if theme:
                theme_counter[theme] += 1
        status_counter[dataset.status] += 1

    catalog_service = service or UnifiedCatalogService()
    table_column_apps = set(catalog_service.get_apps_with_table_columns())
    filtered_dist_names, dist_to_dataset = _build_distribution_index(filtered, table_column_apps)
    column_counter = catalog_service.build_column_counter(filtered_dist_names, dist_to_dataset)

    return FrontendSidebarContext(
        sidebar_keywords=_make_sidebar_items(keyword_counter, filter_state.keywords),
        sidebar_sources=_make_sidebar_items(source_counter, filter_state.source),
        sidebar_custodians=_make_sidebar_items(
            custodian_counter,
            filter_state.custodian,
            label_fn=_agent_label,
        ),
        sidebar_health_categories=_make_sidebar_items(
            health_category_counter,
            filter_state.health_category,
            label_fn=_health_category_label,
        ),
        sidebar_themes=_make_sidebar_items(
            theme_counter,
            filter_state.theme,
            label_fn=_theme_label,
        ),
        sidebar_columns=_make_sidebar_items(column_counter, filter_state.column),
        sidebar_counts=FrontendSidebarCounts(
            ready=status_counter.get('ready', 0),
            raw=status_counter.get('raw', 0),
            unavailable=status_counter.get('unavailable', 0),
        ),
    )
