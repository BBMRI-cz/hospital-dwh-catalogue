"""RDF parsing helpers for FAIR Genomes sync."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fair_genomes.services.rdf_schema import (
    ENTITY_SPECS,
    FieldSpec,
    RawRecord,
    discover_graph_schema,
)


def dedupe_preserve_order(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed
    except (ValueError, TypeError):
        return None


def parse_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _extract_scalar_values(graph, subject, predicates) -> tuple[list[str], list[str]]:
    from rdflib import Literal as RdfLiteral
    from rdflib import URIRef

    literal_values: list[str] = []
    uri_values: list[str] = []

    for predicate in predicates:
        for obj in graph.objects(subject, predicate):
            if isinstance(obj, URIRef):
                uri_values.append(str(obj))
            elif isinstance(obj, RdfLiteral):
                literal_values.append(str(obj))

    return dedupe_preserve_order(literal_values), dedupe_preserve_order(uri_values)


def _normalise_field_value(
    literal_values: list[str],
    uri_values: list[str],
    field: FieldSpec,
) -> Any:
    raw_value: str | None

    if field.extractor == 'literal':
        raw_value = (literal_values or uri_values or [None])[0]
    elif field.extractor == 'uri':
        raw_value = (uri_values or literal_values or [None])[0]
    elif field.extractor == 'multi_uri':
        values = uri_values or literal_values
        raw_value = field.separator.join(values) if values else None
    else:
        values = literal_values or uri_values
        raw_value = field.separator.join(values) if values else None

    if field.value_type == 'datetime':
        return parse_datetime(raw_value)
    if field.value_type == 'int':
        return parse_int(raw_value)
    return raw_value


def parse_raw_records(graph) -> dict[str, list[RawRecord]]:
    schema = discover_graph_schema(graph)
    parsed: dict[str, list[RawRecord]] = {spec.name: [] for spec in ENTITY_SPECS}

    for spec in ENTITY_SPECS:
        for subject in schema.subjects_for_entity(graph, spec.name):
            values: dict[str, object] = {}
            for field in spec.fields:
                predicates = schema.predicate_candidates(spec.name, field)
                literal_values, uri_values = _extract_scalar_values(graph, subject, predicates)
                values[field.name] = _normalise_field_value(literal_values, uri_values, field)

            parsed[spec.name].append(
                RawRecord(
                    entity_name=spec.name,
                    subject_uri=str(subject),
                    values=values,
                )
            )

    return parsed


def resolve_related(
    value: str | None,
    by_uri: dict[str, object],
    by_name: dict[str, object],
):
    if not value:
        return None
    if value in by_uri:
        return by_uri[value]
    return by_name.get(value)
