"""Public HealthDCAT-AP JSON-LD and Turtle export facade."""

from __future__ import annotations

from shared.dtos import ExportCatalog, ExportDataset
from shared.export_context import clear_export_context_cache
from shared.export_graph import JsonLdGraphBuilder
from shared.export_nodes import append_catalog_resource, append_dataset_resource
from shared.export_serialization import dump_jsonld, serialise_jsonld_to_turtle
from shared.export_terms import ResolvedExportProfile
from shared.export_types import (
    ExportResource,
    JsonLdExportResult,
    TurtleExportResult,
)

__all__ = [
    'build_complete_jsonld_result',
    'build_complete_turtle_result',
    'build_jsonld_result',
    'build_turtle_result',
    'clear_export_context_cache',
    'dump_jsonld',
    'has_distributions',
]


def _build_resource_result(resource: ExportResource) -> JsonLdExportResult:
    builder = JsonLdGraphBuilder(ResolvedExportProfile.load())
    if isinstance(resource, ExportDataset):
        append_dataset_resource(resource, builder, include_catalog=False)
    elif isinstance(resource, ExportCatalog):
        append_catalog_resource(resource, builder)
    else:
        raise TypeError(f'Unsupported export resource: {type(resource)!r}')
    return JsonLdExportResult(document=builder.document(), warnings=builder.warnings)


def _build_complete_result(
    catalogs: list[ExportCatalog],
    orphan_datasets: list[ExportDataset],
    *,
    include_distributions: bool = True,
) -> JsonLdExportResult:
    builder = JsonLdGraphBuilder(ResolvedExportProfile.load())

    for catalog in catalogs:
        append_catalog_resource(catalog, builder, include_distributions=include_distributions)

    for dataset in orphan_datasets:
        append_dataset_resource(
            dataset,
            builder,
            include_catalog=False,
            include_distributions=include_distributions,
        )

    return JsonLdExportResult(document=builder.document(), warnings=builder.warnings)


def build_jsonld_result(resource: ExportResource) -> JsonLdExportResult:
    return _build_resource_result(resource)


def build_complete_jsonld_result(
    catalogs: list[ExportCatalog],
    orphan_datasets: list[ExportDataset],
    *,
    include_distributions: bool = True,
) -> JsonLdExportResult:
    return _build_complete_result(
        catalogs,
        orphan_datasets,
        include_distributions=include_distributions,
    )


def has_distributions(dataset: ExportDataset) -> bool:
    return bool(dataset.distributions)


def build_turtle_result(resource: ExportResource) -> TurtleExportResult:
    result = build_jsonld_result(resource)
    return TurtleExportResult(
        content=serialise_jsonld_to_turtle(result.document),
        warnings=result.warnings,
    )


def build_complete_turtle_result(
    catalogs: list[ExportCatalog],
    orphan_datasets: list[ExportDataset],
    *,
    include_distributions: bool = True,
) -> TurtleExportResult:
    result = build_complete_jsonld_result(
        catalogs,
        orphan_datasets,
        include_distributions=include_distributions,
    )
    return TurtleExportResult(
        content=serialise_jsonld_to_turtle(result.document),
        warnings=result.warnings,
    )
