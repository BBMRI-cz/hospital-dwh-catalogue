"""Typed presentation read models for the frontend layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class FrontendDistribution:
    app: str
    name: str
    title: str
    description: str | None
    access_url: str | None
    applicable_legislation: list[str]
    format: str | None
    conforms_to: list[str]
    byte_size: int | None
    rights: str | None
    release_date: str | None
    modification_date: str | None
    licence: str | None
    db_layer: str | None


@dataclass(slots=True)
class FrontendDataset:
    app: str
    name: str
    title: str
    identifier: str | None
    type: list[str]
    access_rights: str | None
    version: str | None
    conforms_to: list[str]
    theme: list[str]
    publisher: str | None
    applicable_legislation: list[str]
    health_category: list[str]
    hdab: str | None
    source: str | None
    creator: str | None
    issued: str | None
    modified: str | None
    contact_point: str | None
    custodian: str | None
    provenance: str | None
    description: str | None
    keywords: list[str]
    catalog_name: str | None
    status: str
    distributions: list[FrontendDistribution] = field(default_factory=list)
    search_text: str = ''

    @property
    def cart_key(self) -> str:
        return f'{self.app}/{self.name}'


@dataclass(slots=True)
class FrontendStatChart:
    label: str
    table_name: str
    column_name: str
    data: dict[str, int]
    canvas_idx: int | None = None


@dataclass(slots=True)
class FrontendStatChartGroup:
    table_name: str
    charts: list[FrontendStatChart]


@dataclass(slots=True)
class FrontendTableColumn:
    name: str
    title: str | None
    description: str | None
    datatype: str | None
    property_url: str | None


@dataclass(slots=True)
class FrontendTable:
    name: str
    title: str
    description: str
    url: str | None
    columns: list[FrontendTableColumn]


@dataclass(slots=True)
class FrontendSidebarItem:
    value: str
    label: str
    count: int
    checked: bool


@dataclass(slots=True)
class FrontendFilterDefinition:
    field_name: str
    label: str
    sort_order: int = 0


@dataclass(slots=True)
class FrontendFilterGroup:
    title: str
    field_name: str
    items: list[FrontendSidebarItem]


@dataclass(slots=True)
class FrontendSidebarCounts:
    ready: int
    raw: int
    unavailable: int


@dataclass(slots=True)
class FrontendSidebarContext:
    filter_groups: list[FrontendFilterGroup]
    sidebar_columns: list[FrontendSidebarItem]
    sidebar_counts: FrontendSidebarCounts


@dataclass(slots=True)
class FrontendMetadataRow:
    field_name: str
    semantics: str
    label: str
    value: Any


@dataclass(slots=True)
class FrontendDatasetCard:
    dataset: FrontendDataset
    preview_rows: list[FrontendMetadataRow]
    can_expand: bool


@dataclass(slots=True)
class FrontendFilterChip:
    display: str
    title: str
    remove_url: str
    container_class: str


@dataclass(slots=True)
class CatalogueDistributionLookup:
    distribution: FrontendDistribution
    dataset: FrontendDataset


@dataclass(slots=True)
class CatalogueSnapshot:
    datasets: list[FrontendDataset]
    datasets_by_key: dict[tuple[str, str], FrontendDataset]
    distributions_by_key: dict[tuple[str, str], CatalogueDistributionLookup]
    total_distribution_count: int


FrontendDcatRow = tuple[str, str, Any]
