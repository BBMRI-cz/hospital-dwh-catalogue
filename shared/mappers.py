"""
Mappers: Django model instances → shared DTOs.

Each mapper function accepts a concrete model instance from one of the
source apps and returns a normalised DTO.  FKs are resolved via
getattr(..., None) guards so that None FKs never raise AttributeError.

Naming convention:
  map_<source>_<entity>  e.g. map_warehouse_dataset, map_fair_dataset
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, cast

from shared.dtos import (
    ExportAgent,
    ExportCatalog,
    ExportColumn,
    ExportContactPoint,
    ExportDataset,
    ExportDistribution,
    ExportTable,
    UnifiedDataset,
    UnifiedDistribution,
)

if TYPE_CHECKING:
    # Import only for type hints — avoids import-time coupling.
    from fair_genomes import models as fgm
    from warehouse import models as wm


_ModelT = TypeVar('_ModelT', covariant=True)


class _RelatedManager(Protocol[_ModelT]):
    def all(self) -> Iterable[_ModelT]: ...


# ── Helpers ──────────────────────────────────────────────────────────────────


def _fk_name(obj: object, fk_attr: str) -> str | None:
    """Return the .name of a FK object, or None if the FK is not set."""
    related = getattr(obj, fk_attr, None)
    return getattr(related, 'name', None) if related else None


def _dt_str(obj: object, attr: str) -> str | None:
    """Return isoformat of a DateTimeField or None."""
    value = getattr(obj, attr, None)
    return value.isoformat() if value else None


def _keywords(value: str | None) -> list[str]:
    """Split a comma-separated keyword string into a clean list."""
    return [item.strip() for item in (value or '').split(',') if item.strip()]


def map_export_contact_point(
    obj: wm.ContactPoint | fgm.ContactPoint, app: str
) -> ExportContactPoint:
    return ExportContactPoint(
        app=app,
        identifier=str(obj.pk),
        email=getattr(obj, 'email', None),
        contact_page=getattr(obj, 'contact_page', None),
    )


def map_export_agent(obj: wm.Agent | fgm.Agent, app: str) -> ExportAgent:
    contact_point = getattr(obj, 'contact_point', None)
    return ExportAgent(
        app=app,
        name=obj.name,
        description=getattr(obj, 'description', None),
        contact_point=map_export_contact_point(contact_point, app) if contact_point else None,
    )


def map_export_catalog(
    obj: wm.Catalog | fgm.Catalog,
    app: str,
    *,
    datasets: list[ExportDataset] | None = None,
) -> ExportCatalog:
    publisher = getattr(obj, 'publisher', None)
    return ExportCatalog(
        app=app,
        name=obj.name,
        title=getattr(obj, 'title', None),
        description=getattr(obj, 'description', None),
        applicable_legislation=getattr(obj, 'applicable_legislation', None),
        publisher=map_export_agent(publisher, app) if publisher else None,
        datasets=datasets or [],
    )


def map_export_column(obj: wm.Column) -> ExportColumn:
    return ExportColumn(
        name=obj.name,
        title=getattr(obj, 'title', None),
        description=getattr(obj, 'description', None),
        datatype=getattr(obj, 'datatype', None),
        property_url=getattr(obj, 'property_url', None),
    )


def map_export_table(obj: wm.Table) -> ExportTable:
    columns_manager = cast(_RelatedManager[Any] | None, getattr(obj, 'columns', None))
    return ExportTable(
        name=obj.name,
        title=getattr(obj, 'title', None),
        description=getattr(obj, 'description', None),
        url=getattr(obj, 'url', None),
        columns=[map_export_column(column) for column in columns_manager.all()]
        if columns_manager
        else [],
    )


def map_export_distribution(
    obj: wm.Distribution | fgm.Distribution, app: str
) -> ExportDistribution:
    tables_manager = cast(_RelatedManager[Any] | None, getattr(obj, 'tables', None))
    tables = [map_export_table(table) for table in tables_manager.all()] if tables_manager else []
    return ExportDistribution(
        app=app,
        name=obj.name,
        title=getattr(obj, 'title', None),
        description=getattr(obj, 'description', None),
        access_url=getattr(obj, 'access_url', None),
        applicable_legislation=getattr(obj, 'applicable_legislation', None),
        format=getattr(obj, 'format', None),
        conforms_to=getattr(obj, 'conforms_to', None),
        byte_size=getattr(obj, 'byte_size', None),
        rights=getattr(obj, 'rights', None),
        release_date=_dt_str(obj, 'release_date'),
        modification_date=_dt_str(obj, 'modification_date'),
        licence=getattr(obj, 'licence', None),
        db_layer=getattr(obj, 'db_layer', None),
        tables=tables,
    )


def map_export_dataset(
    obj: wm.Dataset | fgm.Dataset,
    app: str,
    *,
    include_catalog: bool = True,
) -> ExportDataset:
    publisher = getattr(obj, 'publisher', None)
    creator = getattr(obj, 'creator', None)
    contact_point = getattr(obj, 'contact_point', None)
    catalog = getattr(obj, 'catalog', None)
    hdab = getattr(obj, 'hdab', None)
    custodian = getattr(obj, 'custodian', None)
    source = getattr(obj, 'source', None)
    distributions_manager = cast(
        _RelatedManager[Any] | None,
        getattr(obj, 'distributions', None),
    )
    return ExportDataset(
        app=app,
        name=obj.name,
        title=getattr(obj, 'title', None),
        version=getattr(obj, 'version', None),
        description=getattr(obj, 'description', None),
        identifier=getattr(obj, 'identifier', None),
        type=getattr(obj, 'type', None),
        theme=getattr(obj, 'theme', None),
        publisher=map_export_agent(publisher, app) if publisher else None,
        conforms_to=getattr(obj, 'conforms_to', None),
        issued=_dt_str(obj, 'issued'),
        modified=_dt_str(obj, 'modified'),
        keywords=_keywords(getattr(obj, 'keyword', None)),
        source_name=getattr(source, 'name', None) if source else None,
        source_identifier=getattr(source, 'identifier', None) if source else None,
        creator=map_export_agent(creator, app) if creator else None,
        contact_point=map_export_contact_point(contact_point, app) if contact_point else None,
        provenance=getattr(obj, 'provenance', None),
        catalog=map_export_catalog(catalog, app) if include_catalog and catalog else None,
        access_rights=getattr(obj, 'access_rights', None),
        applicable_legislation=getattr(obj, 'applicable_legislation', None),
        health_category=getattr(obj, 'health_category', None),
        hdab=map_export_agent(hdab, app) if hdab else None,
        custodian=map_export_agent(custodian, app) if custodian else None,
        distributions=[
            map_export_distribution(distribution, app)
            for distribution in distributions_manager.all()
        ]
        if distributions_manager
        else [],
    )


# ── Warehouse (Local Metadata) mappers ────────────────────────────────────────


def map_warehouse_dataset(obj: wm.Dataset) -> UnifiedDataset:
    cp = getattr(obj, 'contact_point', None)
    return UnifiedDataset(
        app='warehouse',
        name=obj.name,
        title=obj.title,
        version=obj.version,
        description=obj.description,
        theme=obj.theme,
        publisher=_fk_name(obj, 'publisher'),
        conforms_to=obj.conforms_to,
        issued=_dt_str(obj, 'issued'),
        modified=_dt_str(obj, 'modified'),
        keyword=obj.keyword,
        source=_fk_name(obj, 'source'),
        creator=_fk_name(obj, 'creator'),
        contact_point=getattr(cp, 'email', None),
        provenance=obj.provenance,
        catalog_name=_fk_name(obj, 'catalog'),
        access_rights=obj.access_rights,
        applicable_legislation=obj.applicable_legislation,
        health_category=obj.health_category,
        hdab=_fk_name(obj, 'hdab'),
        custodian=_fk_name(obj, 'custodian'),
        identifier=getattr(obj, 'identifier', None),
        type=getattr(obj, 'type', None),
    )


def map_warehouse_distribution(obj: wm.Distribution) -> UnifiedDistribution:
    return UnifiedDistribution(
        app='warehouse',
        name=obj.name,
        dataset_name=_fk_name(obj, 'dataset_name'),
        title=obj.title,
        description=obj.description,
        access_url=obj.access_url,
        applicable_legislation=obj.applicable_legislation,
        format=obj.format,
        conforms_to=obj.conforms_to,
        byte_size=obj.byte_size,
        rights=obj.rights,
        release_date=_dt_str(obj, 'release_date'),
        modification_date=_dt_str(obj, 'modification_date'),
        licence=obj.licence,
        db_layer=getattr(obj, 'db_layer', None),
    )


# ── FAIR Genomes mappers ───────────────────────────────────────────────────────


def map_fair_dataset(obj: fgm.Dataset) -> UnifiedDataset:
    cp = getattr(obj, 'contact_point', None)
    return UnifiedDataset(
        app='fair_genomes',
        name=obj.name,
        title=obj.title,
        version=obj.version,
        description=obj.description,
        theme=obj.theme,
        publisher=_fk_name(obj, 'publisher'),
        conforms_to=obj.conforms_to,
        issued=_dt_str(obj, 'issued'),
        modified=_dt_str(obj, 'modified'),
        keyword=obj.keyword,
        source=_fk_name(obj, 'source'),
        creator=_fk_name(obj, 'creator'),
        contact_point=getattr(cp, 'email', None),
        provenance=obj.provenance,
        catalog_name=_fk_name(obj, 'catalog'),
        access_rights=obj.access_rights,
        applicable_legislation=obj.applicable_legislation,
        health_category=obj.health_category,
        hdab=_fk_name(obj, 'hdab'),
        custodian=_fk_name(obj, 'custodian'),
        identifier=obj.identifier,
        type=obj.type,
    )


def map_fair_distribution(obj: fgm.Distribution) -> UnifiedDistribution:
    return UnifiedDistribution(
        app='fair_genomes',
        name=obj.name,
        dataset_name=_fk_name(obj, 'dataset_name'),
        title=obj.title,
        description=obj.description,
        access_url=obj.access_url,
        applicable_legislation=obj.applicable_legislation,
        format=obj.format,
        conforms_to=obj.conforms_to,
        byte_size=obj.byte_size,
        rights=obj.rights,
        release_date=_dt_str(obj, 'release_date'),
        modification_date=_dt_str(obj, 'modification_date'),
        licence=obj.licence,
    )
