"""Typed presentation DTOs for frontend cache and template payloads."""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class FrontendDistributionDTO(TypedDict):
    app: str
    name: str
    title: str
    description: str | None
    access_url: str | None
    applicable_legislation: str | None
    format: str | None
    conforms_to: str | None
    byte_size: int | None
    rights: str | None
    release_date: str | None
    modification_date: str | None
    licence: str | None
    db_layer: str | None


class FrontendDatasetDTO(TypedDict):
    title: str
    access_rights: str | None
    version: str | None
    conforms_to: str | None
    theme: str | None
    publisher: str | None
    applicable_legislation: str | None
    health_category: str | None
    hdab: str | None
    source: str | None
    creator: str | None
    issued: str | None
    modified: str | None
    contact_point: str | None
    custodian: str | None
    provenance: str | None
    app: str
    name: str
    description: str | None
    keywords: list[str]
    catalog: str | None
    status: str
    distributions: list[FrontendDistributionDTO]


class FrontendStatChartDTO(TypedDict):
    label: str
    table_name: str
    column_name: str
    data: dict[str, int]
    canvas_idx: NotRequired[int]


class FrontendStatChartGroupDTO(TypedDict):
    table_name: str
    charts: list[FrontendStatChartDTO]


class FrontendTableColumnDTO(TypedDict):
    name: str
    title: str | None
    description: str | None
    datatype: str | None
    property_url: str | None


class FrontendTableDTO(TypedDict):
    name: str
    title: str
    description: str
    url: str | None
    columns: list[FrontendTableColumnDTO]


class FrontendSidebarItemDTO(TypedDict):
    value: str
    label: str
    count: int
    checked: bool


class FrontendSidebarCountsDTO(TypedDict):
    ready: int
    raw: int
    unavailable: int


class FrontendSidebarContextDTO(TypedDict):
    sidebar_keywords: list[FrontendSidebarItemDTO]
    sidebar_sources: list[FrontendSidebarItemDTO]
    sidebar_custodians: list[FrontendSidebarItemDTO]
    sidebar_health_categories: list[FrontendSidebarItemDTO]
    sidebar_themes: list[FrontendSidebarItemDTO]
    sidebar_columns: list[FrontendSidebarItemDTO]
    sidebar_counts: FrontendSidebarCountsDTO


FrontendDcatRow = tuple[str, str, Any]
