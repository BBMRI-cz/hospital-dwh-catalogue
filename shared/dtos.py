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
