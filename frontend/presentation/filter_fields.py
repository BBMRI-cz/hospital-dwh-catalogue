"""Schema-backed dataset filter field registry and value extraction."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, fields
from typing import Any

from django.db import OperationalError, ProgrammingError

from frontend.models import RESERVED_FILTER_FIELD_NAMES, CatalogueFilterDefinition
from frontend.presentation.mapping import build_dataset_dcat_rows
from frontend.presentation.types import (
    FrontendDataset,
    FrontendFilterDefinition,
    FrontendMetadataRow,
)
from schema_registry.services import get_schema_dict
from schema_registry.types import SchemaRegistryPayload

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


def normalise_filter_values(value: Any) -> list[str]:
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


VALUE_LABELS: dict[str, Callable[[str], str]] = {
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
        if not normalise_filter_values(value):
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
