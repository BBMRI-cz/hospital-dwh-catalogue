"""Support helpers for FAIR Genomes Django admin views and forms."""

import logging

from rdflib import Graph

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

from fair_genomes.models import Dataset, Distribution, FairGenomesSyncState
from fair_genomes.services.client import detect_rdf_format, fetch_rdf
from fair_genomes.services.fair_genomes_service import FairGenomesService
from fair_genomes.services.parser import parse_raw_records
from fair_genomes.services.sync_state import get_state_map

logger = logging.getLogger(__name__)

_SCHEMA_CACHE_KEY = 'fg_molgenis_schema'
_SCHEMA_CACHE_TTL = 300
_RDF_INVENTORY_CACHE_KEY_PREFIX = 'fg_rdf_inventory'
_RDF_INVENTORY_CACHE_TTL = 300


def sync_report_status_label(status: str) -> str:
    labels = {
        'complete': _('Complete'),
        'partial': _('Partial'),
        'failed': _('Failed'),
        'skipped': _('Skipped'),
        'nothing_saved': _('Nothing saved'),
        'unknown': _('Unknown'),
    }
    return str(labels.get(status, status))


def get_molgenis_schema() -> dict[str, list[str]]:
    """Return cached MOLGENIS schema; fall back to an empty schema on errors."""
    cached = cache.get(_SCHEMA_CACHE_KEY)
    if cached is not None:
        return cached

    try:
        svc = FairGenomesService()
        schema = svc.introspect_molgenis_schema()
    except Exception:
        logger.exception('Failed to introspect MOLGENIS schema')
        schema = {}

    cache.set(_SCHEMA_CACHE_KEY, schema, _SCHEMA_CACHE_TTL)
    return schema


def _rdf_inventory_cache_key(url: str) -> str:
    return f'{_RDF_INVENTORY_CACHE_KEY_PREFIX}:{url}'


def get_rdf_source_inventory() -> dict:
    """Return cached RDF source dataset/distribution names without writing to DB."""
    url = getattr(settings, 'FAIR_GENOMES_RDF_URL', '')
    if not url:
        return {
            'status': 'not_configured',
            'source_url': '',
            'datasets': set(),
            'distributions': set(),
            'error': 'FAIR_GENOMES_RDF_URL is not configured.',
        }

    cache_key = _rdf_inventory_cache_key(url)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        response = fetch_rdf(url, timeout=(5, 20))
        graph = Graph()
        graph.parse(data=response.text, format=detect_rdf_format(response))
        records = parse_raw_records(graph)
        inventory = {
            'status': 'available',
            'source_url': url,
            'datasets': {
                str(record.values.get('name'))
                for record in records.get('Dataset', [])
                if record.values.get('name')
            },
            'distributions': {
                str(record.values.get('name'))
                for record in records.get('Distribution', [])
                if record.values.get('name')
            },
            'error': '',
        }
    except Exception as exc:
        logger.warning('Failed to inspect FAIR Genomes RDF source inventory: %s', exc)
        inventory = {
            'status': 'unavailable',
            'source_url': url,
            'datasets': set(),
            'distributions': set(),
            'error': str(exc),
        }

    cache.set(cache_key, inventory, _RDF_INVENTORY_CACHE_TTL)
    return inventory


def clear_rdf_source_inventory_cache() -> None:
    url = getattr(settings, 'FAIR_GENOMES_RDF_URL', '')
    if url:
        cache.delete(_rdf_inventory_cache_key(url))


def get_rdf_inventory_status() -> dict:
    inventory = get_rdf_source_inventory()
    local_distribution_names = set(
        Distribution.objects.using('fair_genomes_db').values_list('name', flat=True)
    )
    local_dataset_names = set(
        Dataset.objects.using('fair_genomes_db').values_list('name', flat=True)
    )

    source_distributions = set(inventory.get('distributions') or set())
    source_datasets = set(inventory.get('datasets') or set())
    missing_local_distributions = sorted(source_distributions - local_distribution_names)
    stale_local_distributions = sorted(local_distribution_names - source_distributions)

    return {
        **inventory,
        'local_dataset_count': len(local_dataset_names),
        'local_distribution_count': len(local_distribution_names),
        'source_dataset_count': len(source_datasets),
        'source_distribution_count': len(source_distributions),
        'missing_local_distributions': missing_local_distributions[:10],
        'missing_local_distribution_count': len(missing_local_distributions),
        'stale_local_distributions': stale_local_distributions[:10],
        'stale_local_distribution_count': len(stale_local_distributions),
    }


def get_sync_state_context() -> list[FairGenomesSyncState]:
    states = get_state_map()
    return [
        states.get(
            source_type,
            FairGenomesSyncState(source_type=source_type),
        )
        for source_type in (
            FairGenomesSyncState.SourceType.RDF_METADATA,
            FairGenomesSyncState.SourceType.STATISTICS,
        )
    ]
