"""
UnifiedCatalogService — loads catalogue entities from all source DBs
and returns normalised DTO lists.

This service is the single integration point for views, APIs, or export
scripts that need to consume catalogue data without caring whether it
originates from the Local Metadata (warehouse) or FAIR Genomes DB.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from collections.abc import Mapping

from schema_registry.types import SchemaRegistryPayload
from shared.dtos import (
    ExportCatalog,
    ExportDataset,
    UnifiedDataset,
    UnifiedDistribution,
    UnifiedStatChart,
    UnifiedTable,
    UnifiedTableColumn,
)
from shared.mappers import (
    map_export_catalog,
    map_export_dataset,
    map_fair_dataset,
    map_fair_distribution,
    map_warehouse_dataset,
    map_warehouse_distribution,
)

logger = logging.getLogger(__name__)

_EXPORT_SOURCE_APPS = ('warehouse', 'fair_genomes')


def parse_keywords(keyword_str: str | None) -> list[str]:
    """Parse a comma-separated keyword string into a clean list."""
    return [keyword.strip() for keyword in (keyword_str or '').split(',') if keyword.strip()]


def parse_multi_values(value_str: str | None) -> list[str]:
    """Parse a semicolon-separated multi-value string into a clean list."""
    return [v.strip() for v in (value_str or '').split(';') if v.strip()]


def derive_status(access_rights: str | None) -> str:
    """Derive the catalogue status from an access-rights URI or label."""
    if not access_rights:
        return 'raw'

    access_rights_upper = access_rights.upper()
    if 'PUBLIC' in access_rights_upper and 'NON' not in access_rights_upper:
        return 'ready'
    if 'NON_PUBLIC' in access_rights_upper or 'NONPUBLIC' in access_rights_upper:
        return 'unavailable'
    if 'CLOSED' in access_rights_upper:
        return 'unavailable'
    return 'raw'


# Apps whose distributions carry structural table/column metadata.
# Used by the sidebar column filter and the export queryset prefetch.
_APPS_WITH_TABLE_COLUMNS: frozenset[str] = frozenset({'warehouse'})


class UnifiedCatalogService:
    """
    Aggregates catalogue data from all registered source apps.

    Usage::

        service = UnifiedCatalogService()
        datasets = service.get_datasets()
        distributions = service.get_distributions()
    """

    def get_apps_with_table_columns(self) -> frozenset[str]:
        """Return source app identifiers that provide structural table/column metadata."""
        return _APPS_WITH_TABLE_COLUMNS

    def get_datasets(self) -> list[UnifiedDataset]:
        """
        Return a merged list of UnifiedDataset DTOs from all sources.

        Sources are queried lazily so that a failure in one DB does not
        prevent data from the other from being returned.
        """
        results: list[UnifiedDataset] = []

        # ── Local Metadata (warehouse) ──────────────────────────────────────
        try:
            from warehouse.models import Dataset as WarehouseDataset

            results.extend(
                map_warehouse_dataset(obj)
                for obj in WarehouseDataset.objects.using('metadata_db').select_related(
                    'publisher', 'contact_point', 'catalog', 'hdab'
                )
            )
        except Exception:
            logger.exception('Failed to load warehouse datasets')

        # ── FAIR Genomes ────────────────────────────────────────────────────
        try:
            from fair_genomes.models import Dataset as FairDataset

            results.extend(
                map_fair_dataset(obj)
                for obj in FairDataset.objects.using('fair_genomes_db').select_related(
                    'publisher', 'contact_point', 'catalog', 'hdab'
                )
            )
        except Exception:
            logger.exception('Failed to load fair_genomes datasets')

        logger.info('Loaded %d datasets', len(results))
        return results

    def get_distributions(self) -> list[UnifiedDistribution]:
        """
        Return a merged list of UnifiedDistribution DTOs from all sources.
        """
        results: list[UnifiedDistribution] = []

        try:
            from warehouse.models import Distribution as WarehouseDistribution

            results.extend(
                map_warehouse_distribution(obj)
                for obj in WarehouseDistribution.objects.using('metadata_db').select_related(
                    'dataset_name'
                )
            )
        except Exception:
            logger.exception('Failed to load warehouse distributions')

        try:
            from fair_genomes.models import Distribution as FairDistribution

            results.extend(
                map_fair_distribution(obj)
                for obj in FairDistribution.objects.using('fair_genomes_db').select_related(
                    'dataset_name'
                )
            )
        except Exception:
            logger.exception('Failed to load fair_genomes distributions')

        logger.info('Loaded %d distributions', len(results))
        return results

    def get_datasets_with_distributions(
        self,
    ) -> list[UnifiedDataset]:
        """
        Return datasets with a ``distributions`` attribute attached to each DTO.

        Each item is a standard UnifiedDataset plus an extra
        ``distributions: list[UnifiedDistribution]`` attribute stapled on so
        that views can pass a single list to the template.
        """
        datasets = self.get_datasets()
        all_dists = self.get_distributions()

        # Group distributions by (app, dataset_name)
        dist_map: dict[tuple[str, str], list[UnifiedDistribution]] = defaultdict(list)
        for d in all_dists:
            if d.dataset_name:
                dist_map[(d.app, d.dataset_name)].append(d)

        for ds in datasets:
            ds.distributions = dist_map.get((ds.app, ds.name), [])

        return datasets

    def get_single_dataset(
        self, app: str, name: str
    ) -> tuple[UnifiedDataset, list[UnifiedDistribution]] | tuple[None, list]:
        """
        Return a (UnifiedDataset, distributions) tuple for a single dataset.

        Returns (None, []) when the dataset is not found.
        """
        datasets = self.get_datasets_with_distributions()
        for ds in datasets:
            if ds.app == app and ds.name == name:
                return ds, ds.distributions
        logger.warning('Dataset not found: app=%s name=%s', app, name)
        return None, []

    def get_schema_json(self) -> SchemaRegistryPayload:
        """
        Return a dict keyed by semantics string (e.g. "dct:title") with term
        metadata loaded from the HealthDCAT-AP submodule.

        Used to populate the schema info modal JS in templates.
        Falls back to an empty dict if the submodule release directory is
        missing or rdflib is not installed.
        """
        try:
            from schema_registry.services import get_schema_dict

            return get_schema_dict()
        except Exception:
            logger.exception('Failed to load schema registry')
            return {}

    def get_dataset_names_by_columns(self, column_titles: set[str]) -> frozenset[str]:
        """Return dataset names whose distributions contain columns matching *column_titles*."""
        if not column_titles:
            return frozenset()
        try:
            from warehouse.services import WarehouseMetadataService

            return WarehouseMetadataService().get_dataset_names_by_columns(column_titles)
        except Exception:
            logger.exception('Failed to resolve dataset names by columns')
            return frozenset()

    def build_column_counter(
        self,
        filtered_dist_names: list[str],
        dist_to_dataset: Mapping[str, str],
    ) -> Counter[str]:
        """Build sidebar column counts for warehouse distributions."""
        if not filtered_dist_names:
            return Counter()
        try:
            from warehouse.services import WarehouseMetadataService

            return WarehouseMetadataService().build_column_counter(
                filtered_dist_names,
                dist_to_dataset,
            )
        except Exception:
            logger.exception('Failed to build column counter')
            return Counter()

    def get_tables_with_columns(self, app: str, distribution_name: str) -> list[UnifiedTable]:
        """Return canonical table/column read models for a distribution.

        Calls WarehouseMetadataService unconditionally — it returns [] naturally
        for distribution names that have no warehouse tables.
        """
        try:
            from warehouse.services import WarehouseMetadataService

            table_payloads = WarehouseMetadataService().get_tables_with_columns(distribution_name)
        except Exception:
            logger.exception(
                'Failed to load warehouse tables for distribution=%s', distribution_name
            )
            return []

        return [
            UnifiedTable(
                name=table['name'],
                title=table['title'],
                description=table['description'],
                url=table['url'],
                columns=[
                    UnifiedTableColumn(
                        name=column['name'],
                        title=column['title'],
                        description=column['description'],
                        datatype=column['datatype'],
                        property_url=column['property_url'],
                    )
                    for column in table['columns']
                ],
            )
            for table in table_payloads
        ]

    def get_stat_charts(self, app: str, distribution_name: str) -> list[UnifiedStatChart]:
        """Return canonical stat chart read models for a distribution.

        Calls WarehouseMetadataService unconditionally — it returns [] naturally
        for distribution names that have no stat chart definitions.
        """
        try:
            from warehouse.services import WarehouseMetadataService

            chart_payloads = WarehouseMetadataService().get_stat_charts(distribution_name)
        except Exception:
            logger.exception('Failed to load stat charts for distribution=%s', distribution_name)
            return []

        return [
            UnifiedStatChart(
                label=chart['label'],
                table_name=chart['table_name'],
                column_name=chart['column_name'],
                data=chart['data'],
            )
            for chart in chart_payloads
        ]

    def _get_export_models(self, app: str):
        """Return ``(db_alias, CatalogModel, DatasetModel)`` for an export source app."""
        if app == 'warehouse':
            from warehouse.models import Catalog as WarehouseCatalog
            from warehouse.models import Dataset as WarehouseDataset

            return 'metadata_db', WarehouseCatalog, WarehouseDataset

        if app == 'fair_genomes':
            from fair_genomes.models import Catalog as FairCatalog
            from fair_genomes.models import Dataset as FairDataset

            return 'fair_genomes_db', FairCatalog, FairDataset

        logger.warning('Unsupported export app requested: %s', app)
        return None, None, None

    def _get_export_dataset_queryset(self, app: str, db_alias: str, dataset_model):
        queryset = dataset_model.objects.using(db_alias).select_related(
            'publisher__contact_point',
            'creator__contact_point',
            'contact_point',
            'catalog__publisher__contact_point',
            'hdab__contact_point',
            'custodian__contact_point',
            'source',
        )

        queryset = queryset.prefetch_related('distributions')
        if app in _APPS_WITH_TABLE_COLUMNS:
            queryset = queryset.prefetch_related('distributions__tables__columns')

        return queryset

    def _get_export_catalog_queryset(self, db_alias: str, catalog_model):
        return catalog_model.objects.using(db_alias).select_related('publisher__contact_point')

    def get_export_dataset(self, app: str, name: str):
        """Return a structured export dataset graph object, or None if missing."""
        db_alias, _, dataset_model = self._get_export_models(app)
        if dataset_model is None or db_alias is None:
            return None

        queryset = self._get_export_dataset_queryset(app, db_alias, dataset_model).filter(name=name)

        dataset = queryset.first()
        if dataset is None:
            logger.warning('Export dataset not found: app=%s name=%s', app, name)
            return None

        return map_export_dataset(dataset, app)

    def get_export_catalog(self, app: str, name: str):
        """Return a structured export catalog graph object, or None if missing."""
        db_alias, catalog_model, dataset_model = self._get_export_models(app)
        if catalog_model is None or dataset_model is None or db_alias is None:
            return None

        catalog = (
            self._get_export_catalog_queryset(db_alias, catalog_model).filter(name=name).first()
        )
        if catalog is None:
            logger.warning('Export catalog not found: app=%s name=%s', app, name)
            return None

        dataset_queryset = self._get_export_dataset_queryset(app, db_alias, dataset_model).filter(
            catalog_id=name
        )

        export_datasets = [
            map_export_dataset(dataset, app, include_catalog=False) for dataset in dataset_queryset
        ]
        return map_export_catalog(catalog, app, datasets=export_datasets)

    def get_complete_export_catalogue(self) -> tuple[list[ExportCatalog], list[ExportDataset]]:
        """Return all exportable catalogs plus datasets not assigned to any catalog."""
        export_catalogs: list[ExportCatalog] = []
        orphan_datasets: list[ExportDataset] = []

        for app in _EXPORT_SOURCE_APPS:
            db_alias, catalog_model, dataset_model = self._get_export_models(app)
            if catalog_model is None or dataset_model is None or db_alias is None:
                continue

            try:
                catalog_rows = list(self._get_export_catalog_queryset(db_alias, catalog_model))
                dataset_rows = list(self._get_export_dataset_queryset(app, db_alias, dataset_model))
            except Exception:
                logger.exception('Failed to load aggregate export resources for app=%s', app)
                continue

            datasets_by_catalog: dict[str, list[ExportDataset]] = defaultdict(list)
            for dataset in dataset_rows:
                export_dataset = map_export_dataset(dataset, app, include_catalog=False)
                catalog_name = getattr(dataset, 'catalog_id', None)
                if catalog_name:
                    datasets_by_catalog[catalog_name].append(export_dataset)
                else:
                    orphan_datasets.append(export_dataset)

            export_catalogs.extend(
                map_export_catalog(
                    catalog,
                    app,
                    datasets=datasets_by_catalog.get(catalog.name, []),
                )
                for catalog in catalog_rows
            )

        return export_catalogs, orphan_datasets
