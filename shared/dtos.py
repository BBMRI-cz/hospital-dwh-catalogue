"""
Unified HealthDCAT-AP Data Transfer Objects (DTOs).

These are plain Python dataclasses — NOT Django models.
They provide a normalised, source-agnostic view of catalogue entities
that can be consumed by views, serialisers, and the API layer without
coupling them to a specific DB model or app.

The `app` field on every DTO carries the originating app label
('warehouse' or 'fair_genomes') so callers can trace provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UnifiedDataset:
    # Required identity fields (no default — must stay first)
    app: str
    name: str
    # DCAT fields — named to match snake_case(schema local_name) so the view
    # can look them up automatically without a separate mapping table.
    title: str | None = None
    access_rights: str | None = None
    version: str | None = None
    conforms_to: str | None = None
    theme: str | None = None
    publisher: str | None = None
    applicable_legislation: str | None = None
    health_category: str | None = None
    hdab: str | None = None
    custodian: str | None = None  # geodcatap:custodian (Release 6, optional)
    source: str | None = None  # dct:source — URI of the origin dataset
    creator: str | None = None
    issued: str | None = None
    modified: str | None = None
    contact_point: str | None = None
    provenance: str | None = None
    # Non-DCAT fields
    description: str | None = None
    keyword: str | None = None
    catalog_name: str | None = None
    # HealthDCAT-AP v6 — new mandatory fields
    identifier: str | None = None  # dct:identifier
    type: str | None = None  # dct:type — EU Dataset-type vocabulary URI(s)
    distributions: list[UnifiedDistribution] = field(default_factory=list)


@dataclass
class UnifiedDistribution:
    app: str
    name: str
    dataset_name: str | None = None
    title: str | None = None
    description: str | None = None
    access_url: str | None = None
    applicable_legislation: str | None = None
    format: str | None = None
    conforms_to: str | None = None
    byte_size: int | None = None
    rights: str | None = None
    release_date: str | None = None
    modification_date: str | None = None
    licence: str | None = None
    # Warehouse-specific; None for FAIR Genomes distributions
    db_layer: str | None = None


@dataclass
class UnifiedTableColumn:
    name: str
    title: str | None = None
    description: str | None = None
    datatype: str | None = None
    property_url: str | None = None


@dataclass
class UnifiedTable:
    name: str
    title: str
    description: str
    url: str | None = None
    columns: list[UnifiedTableColumn] = field(default_factory=list)


@dataclass
class UnifiedStatChart:
    label: str
    table_name: str
    column_name: str
    data: dict[str, int] = field(default_factory=dict)


@dataclass
class ExportContactPoint:
    app: str
    identifier: str
    email: str | None = None
    contact_page: str | None = None


@dataclass
class ExportAgent:
    app: str
    name: str
    description: str | None = None
    contact_point: ExportContactPoint | None = None


@dataclass
class ExportColumn:
    name: str
    title: str | None = None
    description: str | None = None
    datatype: str | None = None
    property_url: str | None = None


@dataclass
class ExportTable:
    name: str
    title: str | None = None
    description: str | None = None
    url: str | None = None
    columns: list[ExportColumn] = field(default_factory=list)


@dataclass
class ExportDistribution:
    app: str
    name: str
    title: str | None = None
    description: str | None = None
    access_url: str | None = None
    applicable_legislation: str | None = None
    format: str | None = None
    conforms_to: str | None = None
    byte_size: int | None = None
    rights: str | None = None
    release_date: str | None = None
    modification_date: str | None = None
    licence: str | None = None
    db_layer: str | None = None
    tables: list[ExportTable] = field(default_factory=list)


@dataclass
class ExportCatalog:
    app: str
    name: str
    title: str | None = None
    description: str | None = None
    applicable_legislation: str | None = None
    publisher: ExportAgent | None = None
    datasets: list[ExportDataset] = field(default_factory=list)


@dataclass
class ExportDataset:
    app: str
    name: str
    title: str | None = None
    version: str | None = None
    description: str | None = None
    identifier: str | None = None
    type: str | None = None
    theme: str | None = None
    publisher: ExportAgent | None = None
    conforms_to: str | None = None
    issued: str | None = None
    modified: str | None = None
    keywords: list[str] = field(default_factory=list)
    source_name: str | None = None
    source_identifier: str | None = None
    creator: ExportAgent | None = None
    contact_point: ExportContactPoint | None = None
    provenance: str | None = None
    catalog: ExportCatalog | None = None
    access_rights: str | None = None
    applicable_legislation: str | None = None
    health_category: str | None = None
    hdab: ExportAgent | None = None
    custodian: ExportAgent | None = None
    distributions: list[ExportDistribution] = field(default_factory=list)
