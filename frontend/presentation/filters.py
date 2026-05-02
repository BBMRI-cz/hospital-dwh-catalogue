"""Filtering, metadata preview, and sidebar builders for the catalogue UI."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, fields
from typing import Any

from django.db import OperationalError, ProgrammingError

from frontend.models import RESERVED_FILTER_FIELD_NAMES
from frontend.presentation.mapping import build_dataset_dcat_rows
from frontend.presentation.types import (
    FrontendDataset,
    FrontendDatasetCard,
    FrontendFilterDefinition,
    FrontendFilterGroup,
    FrontendMetadataRow,
    FrontendSidebarContext,
    FrontendSidebarCounts,
    FrontendSidebarItem,
)
from schema_registry.types import SchemaRegistryPayload
from shared.services import UnifiedCatalogService

_ALL_STATUSES = {'ready', 'raw', 'unavailable'}
_DATASET_FILTER_EXCLUDES = {
    'app',
    'name',
    'description',
    'distributions',
    'search_text',
    'status',
}
_DEFAULT_FILTERS: tuple[FrontendFilterDefinition, ...] = (
    FrontendFilterDefinition('keywords', 'Keywords', 10),
    FrontendFilterDefinition('custodian', 'Custodian', 20),
    FrontendFilterDefinition('health_category', 'Health Category', 30),
    FrontendFilterDefinition('source', 'Source', 40),
    FrontendFilterDefinition('theme', 'Theme', 50),
)


@dataclass(frozen=True, slots=True)
class CatalogueFilterField:
    field_name: str
    semantics: str
    label: str


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


def _to_snake(camel: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', camel).lower()


def _schema_field_to_term(schema_json: SchemaRegistryPayload) -> dict[str, str]:
    return {
        _to_snake(info['local_name']): term
        for term, info in schema_json.items()
        if info.get('local_name')
    }


def _schema_label(schema_json: SchemaRegistryPayload, semantics: str, fallback: str) -> str:
    if semantics in schema_json:
        return schema_json[semantics].get('label') or fallback
    return fallback


def build_supported_filter_field_registry(
    schema_json: SchemaRegistryPayload,
) -> dict[str, CatalogueFilterField]:
    """Return dataset metadata fields that can be used as generic filters."""
    field_to_term = _schema_field_to_term(schema_json)
    registry: dict[str, CatalogueFilterField] = {
        'keywords': CatalogueFilterField(
            field_name='keywords',
            semantics='dcat:keyword',
            label=_schema_label(schema_json, 'dcat:keyword', 'Keywords'),
        )
    }

    for field in fields(FrontendDataset):
        field_name = field.name
        if field_name in _DATASET_FILTER_EXCLUDES or field_name in RESERVED_FILTER_FIELD_NAMES:
            continue
        semantics = field_to_term.get(field_name)
        if not semantics:
            continue
        registry[field_name] = CatalogueFilterField(
            field_name=field_name,
            semantics=semantics,
            label=_schema_label(schema_json, semantics, field_name.replace('_', ' ').title()),
        )

    return registry


def get_supported_filter_field_choices() -> tuple[tuple[str, str], ...]:
    from schema_registry.services import get_schema_dict

    registry = build_supported_filter_field_registry(get_schema_dict())
    return tuple(
        (field.field_name, f'{field.label} ({field.field_name})')
        for field in sorted(registry.values(), key=lambda item: item.label.lower())
    )


def default_filter_definitions(
    schema_json: SchemaRegistryPayload | None = None,
) -> tuple[FrontendFilterDefinition, ...]:
    if schema_json is None:
        return _DEFAULT_FILTERS

    supported = build_supported_filter_field_registry(schema_json)
    return tuple(
        definition for definition in _DEFAULT_FILTERS if definition.field_name in supported
    )


def load_enabled_filter_definitions(
    schema_json: SchemaRegistryPayload,
) -> tuple[FrontendFilterDefinition, ...]:
    """Load enabled filter definitions from DB, skipping unsupported schema fields."""
    supported = build_supported_filter_field_registry(schema_json)
    try:
        from frontend.models import CatalogueFilterDefinition

        definitions = list(
            CatalogueFilterDefinition.objects.filter(is_enabled=True).order_by(
                'sort_order',
                'label',
                'field_name',
            )
        )
    except (OperationalError, ProgrammingError):
        return default_filter_definitions(schema_json)

    return tuple(
        FrontendFilterDefinition(
            field_name=definition.field_name,
            label=definition.label or supported[definition.field_name].label,
            sort_order=definition.sort_order,
        )
        for definition in definitions
        if definition.field_name in supported
    )


def _normalise_filter_values(value: Any) -> list[str]:
    if value is None or value == '':
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, Iterable):
        return [str(item) for item in value if item is not None and str(item)]
    return [str(value)]


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


_VALUE_LABELS: dict[str, Callable[[str], str]] = {
    'custodian': _agent_label,
    'health_category': _health_category_label,
    'theme': _theme_label,
}


def extract_dataset_filter_rows(
    dataset: FrontendDataset,
    schema_json: SchemaRegistryPayload,
) -> dict[str, FrontendMetadataRow]:
    registry = build_supported_filter_field_registry(schema_json)
    term_to_field = {field.semantics: field.field_name for field in registry.values()}
    rows: dict[str, FrontendMetadataRow] = {}

    for semantics, label, value in build_dataset_dcat_rows(schema_json, dataset):
        field_name = term_to_field.get(semantics)
        if not field_name:
            continue
        if not _normalise_filter_values(value):
            continue
        rows[field_name] = FrontendMetadataRow(
            field_name=field_name,
            semantics=semantics,
            label=label,
            value=value,
        )

    if 'keywords' in registry and dataset.keywords:
        field = registry['keywords']
        rows['keywords'] = FrontendMetadataRow(
            field_name='keywords',
            semantics=field.semantics,
            label=field.label,
            value=dataset.keywords,
        )

    return rows


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
            if row is None or not (set(_normalise_filter_values(row.value)) & active):
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
            counters[definition.field_name].update(_normalise_filter_values(row.value))
        status_counter[dataset.status] += 1

    filter_groups = [
        FrontendFilterGroup(
            title=definition.label,
            field_name=definition.field_name,
            items=_make_sidebar_items(
                counters[definition.field_name],
                filter_state.values_for(definition.field_name),
                label_fn=_VALUE_LABELS.get(definition.field_name),
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
