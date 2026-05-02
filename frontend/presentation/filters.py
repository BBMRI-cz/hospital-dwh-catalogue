"""Filtering, metadata preview, and sidebar builders for the catalogue UI."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from frontend.presentation.filter_fields import (
    VALUE_LABELS,
    CatalogueFilterField,
    build_supported_filter_field_registry,
    default_filter_definitions,
    extract_dataset_filter_rows,
    get_supported_filter_field_choices,
    load_enabled_filter_definitions,
    normalise_filter_values,
)
from frontend.presentation.types import (
    FrontendDataset,
    FrontendDatasetCard,
    FrontendFilterDefinition,
    FrontendFilterGroup,
    FrontendSidebarContext,
    FrontendSidebarCounts,
    FrontendSidebarItem,
)
from schema_registry.types import SchemaRegistryPayload
from shared.services import UnifiedCatalogService

__all__ = (
    'CatalogueFilterField',
    'FilterState',
    'build_dataset_cards',
    'build_sidebar_context',
    'build_supported_filter_field_registry',
    'default_filter_definitions',
    'extract_dataset_filter_rows',
    'filter_datasets',
    'get_supported_filter_field_choices',
    'load_enabled_filter_definitions',
)

_ALL_STATUSES = {'ready', 'raw', 'unavailable'}


@dataclass(slots=True)
class FilterState:
    q: str
    status: set[str]
    column: set[str]
    filters: dict[str, set[str]]
    filter_labels: dict[str, str]
    filter_order: tuple[str, ...]

    @classmethod
    def from_query_params(
        cls,
        query_params,
        *,
        filter_definitions: Iterable[FrontendFilterDefinition] | None = None,
    ) -> FilterState:
        definitions = (
            tuple(filter_definitions)
            if filter_definitions is not None
            else default_filter_definitions()
        )
        selected_filters: dict[str, set[str]] = {}
        filter_labels: dict[str, str] = {}
        filter_order: list[str] = []

        for definition in definitions:
            values = {value for value in query_params.getlist(definition.field_name) if value}
            if values:
                selected_filters[definition.field_name] = values
            filter_labels[definition.field_name] = definition.label
            filter_order.append(definition.field_name)

        return cls(
            q=query_params.get('q', ''),
            status=set(query_params.getlist('status')),
            column=set(query_params.getlist('column')),
            filters=selected_filters,
            filter_labels=filter_labels,
            filter_order=tuple(filter_order),
        )

    def values_for(self, field_name: str) -> set[str]:
        return self.filters.get(field_name, set())

    @property
    def keywords(self) -> set[str]:
        return self.values_for('keywords')

    @property
    def source(self) -> set[str]:
        return self.values_for('source')

    @property
    def custodian(self) -> set[str]:
        return self.values_for('custodian')

    @property
    def health_category(self) -> set[str]:
        return self.values_for('health_category')

    @property
    def theme(self) -> set[str]:
        return self.values_for('theme')


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


def filter_datasets(
    datasets: list[FrontendDataset],
    filter_state: FilterState,
    *,
    schema_json: SchemaRegistryPayload | None = None,
    filter_definitions: Iterable[FrontendFilterDefinition] | None = None,
    service: UnifiedCatalogService | None = None,
) -> list[FrontendDataset]:
    schema = schema_json or {}
    definitions = (
        tuple(filter_definitions)
        if filter_definitions is not None
        else default_filter_definitions(schema)
    )
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
        if matching_dataset_names is not None and dataset.name not in matching_dataset_names:
            continue

        rows = extract_dataset_filter_rows(dataset, schema)
        filter_mismatch = False
        for definition in definitions:
            active = filter_state.values_for(definition.field_name)
            if not active:
                continue
            row = rows.get(definition.field_name)
            if row is None or not (set(normalise_filter_values(row.value)) & active):
                filter_mismatch = True
                break
        if filter_mismatch:
            continue

        if query and query not in dataset.search_text:
            continue
        result.append(dataset)

    return result


def build_sidebar_context(
    filtered: list[FrontendDataset],
    *,
    filter_state: FilterState,
    schema_json: SchemaRegistryPayload | None = None,
    filter_definitions: Iterable[FrontendFilterDefinition] | None = None,
    service: UnifiedCatalogService | None = None,
) -> FrontendSidebarContext:
    schema = schema_json or {}
    definitions = (
        tuple(filter_definitions)
        if filter_definitions is not None
        else default_filter_definitions(schema)
    )
    counters: dict[str, Counter[str]] = {
        definition.field_name: Counter() for definition in definitions
    }
    status_counter: Counter[str] = Counter()

    for dataset in filtered:
        rows = extract_dataset_filter_rows(dataset, schema)
        for definition in definitions:
            row = rows.get(definition.field_name)
            if row is None:
                continue
            counters[definition.field_name].update(normalise_filter_values(row.value))
        status_counter[dataset.status] += 1

    filter_groups = [
        FrontendFilterGroup(
            title=definition.label,
            field_name=definition.field_name,
            items=_make_sidebar_items(
                counters[definition.field_name],
                filter_state.values_for(definition.field_name),
                label_fn=VALUE_LABELS.get(definition.field_name),
            ),
        )
        for definition in definitions
    ]

    catalog_service = service or UnifiedCatalogService()
    table_column_apps = set(catalog_service.get_apps_with_table_columns())
    filtered_dist_names, dist_to_dataset = _build_distribution_index(filtered, table_column_apps)
    column_counter = catalog_service.build_column_counter(filtered_dist_names, dist_to_dataset)

    return FrontendSidebarContext(
        filter_groups=filter_groups,
        sidebar_columns=_make_sidebar_items(column_counter, filter_state.column),
        sidebar_counts=FrontendSidebarCounts(
            ready=status_counter.get('ready', 0),
            raw=status_counter.get('raw', 0),
            unavailable=status_counter.get('unavailable', 0),
        ),
    )


def build_dataset_cards(
    datasets: list[FrontendDataset],
    *,
    schema_json: SchemaRegistryPayload,
    filter_definitions: Iterable[FrontendFilterDefinition],
) -> list[FrontendDatasetCard]:
    definitions = tuple(filter_definitions)
    cards: list[FrontendDatasetCard] = []
    for dataset in datasets:
        rows = extract_dataset_filter_rows(dataset, schema_json)
        preview_rows = [
            rows[definition.field_name]
            for definition in definitions
            if definition.field_name in rows
        ]
        cards.append(
            FrontendDatasetCard(
                dataset=dataset,
                preview_rows=preview_rows,
                can_expand=bool(preview_rows),
            )
        )
    return cards
