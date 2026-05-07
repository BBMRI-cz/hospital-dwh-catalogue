"""Persistence helpers for FAIR Genomes RDF sync."""

from __future__ import annotations

import logging
from datetime import datetime

from fair_genomes.models import Agent, Catalog, ContactPoint, Dataset, Distribution
from fair_genomes.services.parser import parse_raw_records, resolve_related
from fair_genomes.services.rdf_schema import RawRecord

logger = logging.getLogger(__name__)


def empty_rdf_report() -> dict:
    return {
        'status': 'partial',
        'rdf_url': '',
        'fetched': {
            'contact_points': [],
            'agents': [],
            'catalogs': [],
            'datasets': [],
            'distributions': [],
        },
        'saved': {
            'contact_points': {'created': [], 'updated': []},
            'agents': {'created': [], 'updated': []},
            'catalogs': {'created': [], 'updated': []},
            'datasets': {'created': [], 'updated': []},
            'distributions': {'created': [], 'updated': []},
        },
        'skipped': {},
    }


def process_graph(graph, *, rdf_url: str) -> dict:
    raw_records = parse_raw_records(graph)
    report = empty_rdf_report()
    report['rdf_url'] = rdf_url

    cp_by_uri: dict[str, ContactPoint] = {}
    agent_by_name: dict[str, Agent] = {}
    agent_by_uri: dict[str, Agent] = {}
    catalog_by_name: dict[str, Catalog] = {}
    catalog_by_uri: dict[str, Catalog] = {}
    dataset_by_name: dict[str, Dataset] = {}
    dataset_by_uri: dict[str, Dataset] = {}

    def str_value(record: RawRecord, field_name: str) -> str | None:
        value = record.values.get(field_name)
        return value if isinstance(value, str) and value else None

    def datetime_value(record: RawRecord, field_name: str) -> datetime | None:
        value = record.values.get(field_name)
        return value if isinstance(value, datetime) else None

    def int_value(record: RawRecord, field_name: str) -> int | None:
        value = record.values.get(field_name)
        return value if isinstance(value, int) else None

    for record in raw_records['ContactPoint']:
        email = str_value(record, 'email')
        contact_page = str_value(record, 'contact_page')
        if not email and not contact_page:
            logger.warning('Skipping ContactPoint with no email or page: %s', record.subject_uri)
            continue

        label = email or contact_page or record.subject_uri
        report['fetched']['contact_points'].append(label)
        contact_point, created = ContactPoint.objects.using('fair_genomes_db').get_or_create(
            email=email,
            contact_page=contact_page,
        )
        report['saved']['contact_points']['created' if created else 'updated'].append(label)
        cp_by_uri[record.subject_uri] = contact_point

    for record in raw_records['Agent']:
        name = str_value(record, 'name')
        if not name:
            logger.warning('Skipping Agent with no name: %s', record.subject_uri)
            continue

        report['fetched']['agents'].append(name)
        agent, created = Agent.objects.using('fair_genomes_db').update_or_create(
            name=name,
            defaults={
                'description': str_value(record, 'description') or '',
                'contact_point': cp_by_uri.get(str_value(record, 'contact_point') or ''),
            },
        )
        report['saved']['agents']['created' if created else 'updated'].append(name)
        agent_by_name[name] = agent
        agent_by_uri[record.subject_uri] = agent

    for record in raw_records['Catalog']:
        name = str_value(record, 'name')
        if not name:
            logger.warning('Skipping Catalog with no name: %s', record.subject_uri)
            continue

        report['fetched']['catalogs'].append(name)
        catalog, created = Catalog.objects.using('fair_genomes_db').update_or_create(
            name=name,
            defaults={
                'title': str_value(record, 'title') or '',
                'description': str_value(record, 'description') or '',
                'publisher': resolve_related(
                    str_value(record, 'publisher'),
                    agent_by_uri,
                    agent_by_name,
                ),
                'applicable_legislation': str_value(record, 'applicable_legislation') or '',
            },
        )
        report['saved']['catalogs']['created' if created else 'updated'].append(name)
        catalog_by_name[name] = catalog
        catalog_by_uri[record.subject_uri] = catalog

    pending_source_refs: list[tuple[Dataset, str]] = []
    for record in raw_records['Dataset']:
        name = str_value(record, 'name')
        if not name:
            logger.warning('Skipping Dataset with no name: %s', record.subject_uri)
            continue

        report['fetched']['datasets'].append(name)

        hdab_ref = str_value(record, 'hdab')
        hdab = resolve_related(hdab_ref, agent_by_uri, agent_by_name)
        contact_point_ref = str_value(record, 'contact_point')
        contact_point = cp_by_uri.get(contact_point_ref or '')

        if not hdab:
            logger.warning('Skipping Dataset "%s": hdab agent "%s" not found', name, hdab_ref)
            report['skipped'].setdefault('datasets', []).append(
                {'name': name, 'reason': 'hdab agent not resolved'}
            )
            continue
        if not contact_point:
            logger.warning(
                'Skipping Dataset "%s": contact_point "%s" not found',
                name,
                contact_point_ref,
            )
            report['skipped'].setdefault('datasets', []).append(
                {'name': name, 'reason': f'contact_point "{contact_point_ref}" not resolved'}
            )
            continue

        source_ref = str_value(record, 'source')
        dataset, created = Dataset.objects.using('fair_genomes_db').update_or_create(
            name=name,
            defaults={
                'title': str_value(record, 'title') or '',
                'version': str_value(record, 'version') or '',
                'description': str_value(record, 'description') or '',
                'identifier': str_value(record, 'identifier') or record.subject_uri,
                'type': str_value(record, 'type') or '',
                'theme': str_value(record, 'theme') or '',
                'keyword': str_value(record, 'keyword') or '',
                'provenance': str_value(record, 'provenance') or '',
                'conforms_to': str_value(record, 'conforms_to') or '',
                'access_rights': str_value(record, 'access_rights') or '',
                'applicable_legislation': str_value(record, 'applicable_legislation') or '',
                'health_category': str_value(record, 'health_category') or '',
                'issued': datetime_value(record, 'issued'),
                'modified': datetime_value(record, 'modified'),
                'hdab': hdab,
                'contact_point': contact_point,
                'publisher': resolve_related(
                    str_value(record, 'publisher'),
                    agent_by_uri,
                    agent_by_name,
                ),
                'creator': resolve_related(
                    str_value(record, 'creator'),
                    agent_by_uri,
                    agent_by_name,
                ),
                'custodian': resolve_related(
                    str_value(record, 'custodian'),
                    agent_by_uri,
                    agent_by_name,
                ),
                'catalog': resolve_related(
                    str_value(record, 'catalog'),
                    catalog_by_uri,
                    catalog_by_name,
                ),
                'source': resolve_related(source_ref, dataset_by_uri, dataset_by_name),
            },
        )
        report['saved']['datasets']['created' if created else 'updated'].append(name)
        dataset_by_name[name] = dataset
        dataset_by_uri[record.subject_uri] = dataset
        if source_ref:
            pending_source_refs.append((dataset, source_ref))

    for dataset, source_ref in pending_source_refs:
        source = resolve_related(source_ref, dataset_by_uri, dataset_by_name)
        if source is None or dataset.source_id == source.pk:
            continue
        dataset.source = source
        dataset.save(update_fields=['source'], using='fair_genomes_db')

    for record in raw_records['Distribution']:
        name = str_value(record, 'name')
        if not name:
            logger.warning('Skipping Distribution with no name: %s', record.subject_uri)
            continue

        report['fetched']['distributions'].append(name)
        dataset_ref = str_value(record, 'dataset_name')
        dataset = resolve_related(dataset_ref, dataset_by_uri, dataset_by_name)
        if not dataset:
            logger.warning('Skipping Distribution "%s": dataset "%s" not found', name, dataset_ref)
            report['skipped'].setdefault('distributions', []).append(
                {'name': name, 'reason': f'dataset "{dataset_ref}" not resolved'}
            )
            continue

        _, created = Distribution.objects.using('fair_genomes_db').update_or_create(
            name=name,
            defaults={
                'dataset_name': dataset,
                'title': str_value(record, 'title') or '',
                'description': str_value(record, 'description') or '',
                'format': str_value(record, 'format') or '',
                'conforms_to': str_value(record, 'conforms_to') or '',
                'byte_size': int_value(record, 'byte_size'),
                'rights': str_value(record, 'rights') or '',
                'release_date': datetime_value(record, 'release_date'),
                'modification_date': datetime_value(record, 'modification_date'),
                'access_url': str_value(record, 'access_url') or '',
                'applicable_legislation': str_value(record, 'applicable_legislation') or '',
                'licence': str_value(record, 'licence') or '',
            },
        )
        report['saved']['distributions']['created' if created else 'updated'].append(name)

    fetched_datasets = set(report['fetched']['datasets'])
    if fetched_datasets:
        deleted_datasets, _ = (
            Dataset.objects.using('fair_genomes_db').exclude(name__in=fetched_datasets).delete()
        )
        if deleted_datasets:
            logger.info('Removed %d stale Dataset(s) not present in current RDF', deleted_datasets)
            report.setdefault('deleted', {})['datasets'] = deleted_datasets

    fetched_distributions = set(report['fetched']['distributions'])
    if fetched_distributions:
        deleted_distributions, _ = (
            Distribution.objects.using('fair_genomes_db')
            .exclude(name__in=fetched_distributions)
            .delete()
        )
        if deleted_distributions:
            logger.info(
                'Removed %d stale Distribution(s) not present in current RDF',
                deleted_distributions,
            )
            report.setdefault('deleted', {})['distributions'] = deleted_distributions

    entity_types = ('contact_points', 'agents', 'catalogs', 'datasets', 'distributions')
    any_saved = any(
        report['saved'][entity][operation]
        for entity in entity_types
        for operation in ('created', 'updated')
    )
    any_skipped = bool(report['skipped'])
    if any_saved and not any_skipped:
        report['status'] = 'complete'
    elif any_saved:
        report['status'] = 'partial'
    else:
        report['status'] = 'nothing_saved'

    return report
