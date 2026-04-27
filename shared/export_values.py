"""JSON-LD value coercion helpers for metadata exports."""

from __future__ import annotations

import re
from typing import Any

from shared.export_terms import ExportValueKind, ResolvedExportProfile
from shared.export_types import JsonLdIdRef, JsonLdLiteralOrUri, JsonLdTypedValue

_IRI_LABEL_RE = re.compile(r'[/#]([^/#]+)[/#]?$')


def split_values(value: str | None) -> list[str]:
    return [item.strip() for item in (value or '').split(';') if item.strip()]


def is_http_uri(value: str | None) -> bool:
    if not value:
        return False
    return value.startswith('http://') or value.startswith('https://')


def id_ref(value: str) -> JsonLdIdRef:
    return {'@id': value}


def maybe_uri_ref(value: str | None) -> JsonLdLiteralOrUri | None:
    if not value:
        return None
    if is_http_uri(value):
        return id_ref(value)
    return value


def typed_value(value_type: str, value: str) -> JsonLdTypedValue:
    return {'@type': value_type, '@value': value}


def typed_any_uri(
    value: str | None,
    profile: ResolvedExportProfile,
) -> JsonLdTypedValue | None:
    if not value:
        return None
    value_type = profile.prefixed_name('xsd', 'anyURI')
    return typed_value(value_type, value) if value_type is not None else None


def typed_datetime(
    value: str | None,
    profile: ResolvedExportProfile,
) -> JsonLdTypedValue | None:
    if not value:
        return None
    value_type = profile.prefixed_name('xsd', 'dateTime')
    return typed_value(value_type, value) if value_type is not None else None


def typed_non_negative_integer(
    value: int | None,
    profile: ResolvedExportProfile,
) -> JsonLdTypedValue | None:
    if value is None:
        return None
    value_type = profile.prefixed_name('xsd', 'nonNegativeInteger')
    return typed_value(value_type, str(value)) if value_type is not None else None


def label_from_iri(iri: str) -> str:
    match = _IRI_LABEL_RE.search(iri)
    if not match:
        return iri
    return match.group(1).replace('_', ' ').replace('-', ' ')


def values_for_reference_nodes(values: object) -> list[str]:
    if isinstance(values, str):
        return [value for value in split_values(values) if is_http_uri(value)]
    if isinstance(values, list):
        return [value for value in values if isinstance(value, str) and is_http_uri(value)]
    return []


def literal_or_id_list(values: str | None) -> list[JsonLdLiteralOrUri]:
    return [id_ref(value) if is_http_uri(value) else value for value in split_values(values)]


def id_list(values: str | None) -> list[JsonLdIdRef]:
    return [id_ref(value) for value in split_values(values) if is_http_uri(value)]


def jsonld_field_value(
    value: Any,
    kind: ExportValueKind,
    profile: ResolvedExportProfile,
):
    if kind == ExportValueKind.LITERAL:
        return value if value not in (None, '') else None
    if kind == ExportValueKind.KEYWORD_LIST:
        return value or None
    if kind == ExportValueKind.ID:
        return id_ref(value) if value else None
    if kind == ExportValueKind.ID_LIST:
        values = id_list(value)
        return values or None
    if kind == ExportValueKind.LITERAL_OR_ID:
        return maybe_uri_ref(value)
    if kind == ExportValueKind.LITERAL_OR_ID_LIST:
        values = literal_or_id_list(value)
        return values or None
    if kind == ExportValueKind.TYPED_ANY_URI:
        return typed_any_uri(value, profile)
    if kind == ExportValueKind.TYPED_DATETIME:
        return typed_datetime(value, profile)
    if kind == ExportValueKind.TYPED_NON_NEGATIVE_INTEGER:
        return typed_non_negative_integer(value, profile)
    raise ValueError(f'Unsupported export value kind: {kind!r}')
