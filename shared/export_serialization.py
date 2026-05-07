"""Serialization helpers for HealthDCAT-AP export documents."""

from __future__ import annotations

import json

from rdflib import Graph  # type: ignore[import-untyped]

from shared.export_types import JsonLdDocument


def dump_jsonld(document: JsonLdDocument) -> str:
    """Serialise a JSON-LD document to a stable pretty-printed string."""
    return json.dumps(document, indent=2, ensure_ascii=False)


def serialise_jsonld_to_turtle(document: JsonLdDocument) -> str:
    """Serialise a JSON-LD document to Turtle."""
    graph = Graph()
    graph.parse(data=dump_jsonld(document), format='json-ld')
    return graph.serialize(format='turtle')
