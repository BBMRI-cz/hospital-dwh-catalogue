"""Typed JSON-LD payloads used by HealthDCAT-AP export helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Required, TypedDict

from shared.dtos import ExportCatalog, ExportDataset

ExportResource = ExportDataset | ExportCatalog

JsonLdContext = dict[str, str]
JsonLdScalar = str | int | float | bool | None
JsonLdValue = JsonLdScalar | dict[str, Any] | list[Any]
JsonLdNode = dict[str, Any]

JsonLdIdRef = TypedDict('JsonLdIdRef', {'@id': Required[str]})

JsonLdTypedValue = TypedDict(
    'JsonLdTypedValue',
    {
        '@type': Required[str],
        '@value': Required[str],
    },
)

JsonLdLiteralOrUri = str | JsonLdIdRef
JsonLdGraph = list[JsonLdNode]

JsonLdDocument = TypedDict(
    'JsonLdDocument',
    {
        '@context': Required[JsonLdContext],
        '@graph': Required[JsonLdGraph],
    },
)


@dataclass(frozen=True, slots=True)
class ExportWarning:
    """Non-fatal warning produced while building a metadata export."""

    code: str
    message: str
    severity: str = 'warning'
    entity: str | None = None
    alias: str | None = None


@dataclass(frozen=True, slots=True)
class JsonLdExportResult:
    """JSON-LD export document with non-fatal export warnings."""

    document: JsonLdDocument
    warnings: tuple[ExportWarning, ...]


@dataclass(frozen=True, slots=True)
class TurtleExportResult:
    """Turtle export content with non-fatal export warnings."""

    content: str
    warnings: tuple[ExportWarning, ...]
