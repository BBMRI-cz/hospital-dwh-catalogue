"""Service layer for the FAIR Genomes catalogue sync."""

import logging
import time
from datetime import UTC, datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from django.conf import settings
from django.db import transaction

from fair_genomes.services.rdf_schema import (
    ENTITY_SPECS,
    FieldSpec,
    RawRecord,
    discover_graph_schema,
)

logger = logging.getLogger(__name__)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    """Return values with duplicates removed while preserving first-seen order."""
    return list(dict.fromkeys(values))


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _extract_scalar_values(graph, subject, predicates) -> tuple[list[str], list[str]]:
    from rdflib import Literal as RdfLiteral
    from rdflib import URIRef

    literal_values: list[str] = []
    uri_values: list[str] = []

    for predicate in predicates:
        for obj in graph.objects(subject, predicate):
            if isinstance(obj, URIRef):
                uri_values.append(str(obj))
            elif isinstance(obj, RdfLiteral):
                literal_values.append(str(obj))

    return _dedupe_preserve_order(literal_values), _dedupe_preserve_order(uri_values)


def _normalise_field_value(literal_values: list[str], uri_values: list[str], field: FieldSpec):
    raw_value: str | None

    if field.extractor == 'literal':
        raw_value = (literal_values or uri_values or [None])[0]
    elif field.extractor == 'uri':
        raw_value = (uri_values or literal_values or [None])[0]
    elif field.extractor == 'multi_uri':
        values = uri_values or literal_values
        raw_value = field.separator.join(values) if values else None
    else:
        values = literal_values or uri_values
        raw_value = field.separator.join(values) if values else None

    if field.value_type == 'datetime':
        return _parse_datetime(raw_value)
    if field.value_type == 'int':
        return _parse_int(raw_value)
    return raw_value


def _parse_raw_records(graph) -> dict[str, list[RawRecord]]:
    schema = discover_graph_schema(graph)
    parsed: dict[str, list[RawRecord]] = {spec.name: [] for spec in ENTITY_SPECS}

    for spec in ENTITY_SPECS:
        for subject in schema.subjects_for_entity(graph, spec.name):
            values: dict[str, object] = {}
            for field in spec.fields:
                predicates = schema.predicate_candidates(spec.name, field)
                literal_values, uri_values = _extract_scalar_values(graph, subject, predicates)
                values[field.name] = _normalise_field_value(literal_values, uri_values, field)

            parsed[spec.name].append(
                RawRecord(
                    entity_name=spec.name,
                    subject_uri=str(subject),
                    values=values,
                )
            )

    return parsed


def _resolve_related(value: str | None, by_uri: dict[str, object], by_name: dict[str, object]):
    if not value:
        return None
    if value in by_uri:
        return by_uri[value]
    return by_name.get(value)


class FairGenomesAPIException(Exception):
    """Raised when the FDP endpoint cannot be reached or its data cannot be parsed."""

    pass


class FairGenomesService:
    """Sync Fair Genomes catalogue data from RDF (FDP) and GraphQL (MOLGENIS)."""

    def __init__(
        self,
        rdf_url: str | None = None,
        api_url: str | None = None,
        api_token: str | None = None,
        timeout: tuple[int, int] | int = (10, 60),
    ):
        # None → fall back to settings; explicit value (even '') → use as-is
        def _cfg(val: str | None, key: str) -> str:
            return val if val is not None else getattr(settings, key, '')

        self.rdf_url = _cfg(rdf_url, 'FAIR_GENOMES_RDF_URL')
        self.graphql_url = _cfg(api_url, 'FAIR_GENOMES_API_URL')
        self.api_token = _cfg(api_token, 'FAIR_GENOMES_API_TOKEN')
        self.timeout = timeout

    # ─────────────────────────────────────────────────────────────────────────
    # Public interface
    # ─────────────────────────────────────────────────────────────────────────

    def sync(self) -> dict:
        """
        Fetch data from all configured sources, then persist everything in one
        atomic transaction so the catalogue is never left in a partial state.

        Sources:
          - RDF (FDP)       : FAIR_GENOMES_RDF_URL
          - GraphQL (MOLGENIS): FAIR_GENOMES_API_URL + FAIR_GENOMES_API_TOKEN

        Returns a structured report dict with the following top-level keys:
            status                    — 'complete' | 'partial' | 'nothing_saved' | 'skipped'
            rdf_url                   — the RDF URL that was fetched (empty if not configured)
            graphql_url               — the GraphQL URL used for stats (empty if not configured)
            fetched                   — names of RDF entities found per type
            saved                     — created/updated counts per entity type
            skipped                   — entities skipped due to unresolved FKs
            stats                     — stat sync results (updated/failed/errors)
            duration_seconds          — wall-clock sync duration

        Raises:
            FairGenomesAPIException: if any network fetch or parse step fails.
        """
        if not self.rdf_url and not self.graphql_url:
            return {
                'status': 'skipped',
                'reason': (
                    'Neither FAIR_GENOMES_RDF_URL nor FAIR_GENOMES_API_URL is configured '
                    '— set at least one in the environment'
                ),
            }

        t0 = time.monotonic()
        logger.info(
            'Sync started',
            extra={'rdf_url': self.rdf_url, 'graphql_url': self.graphql_url},
        )

        # ── Phase 1: all network calls outside the transaction ────────────────
        graph = None
        if self.rdf_url:
            response = self._fetch(self.rdf_url)
            rdf_format = self._detect_format(response)
            try:
                from rdflib import Graph

                graph = Graph()
                graph.parse(data=response.text, format=rdf_format)
            except Exception as exc:
                raise FairGenomesAPIException(
                    f'Failed to parse RDF from {self.rdf_url}: {exc}'
                ) from exc
            logger.info('RDF fetched and parsed', extra={'triples': len(graph)})

        # ── Phase 2: all DB writes in one atomic transaction ──────────────────
        with transaction.atomic(using='fair_genomes_db'):
            report = self._process_graph(graph) if graph else self._empty_rdf_report()

        report['graphql_url'] = self.graphql_url or ''

        # ── Phase 3: stat aggregation — outside transaction so a failed query
        # never rolls back the RDF sync that just completed successfully.
        if self.graphql_url:
            report['stats'] = self._sync_stats()
        else:
            report['stats'] = None

        duration = round(time.monotonic() - t0, 2)
        report['duration_seconds'] = duration
        logger.info(
            'Sync completed',
            extra={'status': report['status'], 'duration_seconds': duration},
        )

        return report

    def close(self) -> None:
        """No-op: retained for interface compatibility."""

    def __enter__(self) -> 'FairGenomesService':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _empty_rdf_report() -> dict:
        """Return a report skeleton used when RDF sync is skipped (stats-only path)."""
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

    def _fetch(self, url: str) -> requests.Response:
        """HTTP GET with an RDF-friendly Accept header and automatic retry on transient errors."""
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=['GET'],
            raise_on_status=False,
        )
        session = requests.Session()
        session.mount('https://', HTTPAdapter(max_retries=retry))
        session.mount('http://', HTTPAdapter(max_retries=retry))
        try:
            response = session.get(
                url,
                timeout=self.timeout,
                headers={'Accept': 'text/turtle, application/rdf+xml;q=0.9, */*;q=0.1'},
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise FairGenomesAPIException(f'Failed to fetch RDF from {url}: {exc}') from exc
        return response

    @staticmethod
    def _detect_format(response: requests.Response) -> str:
        """Detect the RDF serialisation format from Content-Type or body sniffing."""
        ct = response.headers.get('Content-Type', '')
        if 'turtle' in ct or ct.startswith('text/plain'):
            return 'turtle'
        if 'rdf+xml' in ct or 'application/xml' in ct:
            return 'xml'
        if 'n-triples' in ct:
            return 'nt'
        if 'json' in ct:
            return 'json-ld'
        # Sniff first non-whitespace characters
        snippet = response.text.strip()[:60]
        if snippet.startswith('@prefix') or snippet.startswith('@base'):
            return 'turtle'
        if snippet.startswith('<?xml') or '<rdf:RDF' in snippet:
            return 'xml'
        return 'turtle'  # MOLGENIS FDP default

    def _process_graph(self, g) -> dict:
        """Parse the RDF graph into raw records and persist them in FK order."""
        from fair_genomes.models import (
            Agent,
            Catalog,
            ContactPoint,
            Dataset,
            Distribution,
        )

        raw_records = _parse_raw_records(g)

        report: dict = {
            'status': 'partial',
            'rdf_url': self.rdf_url,
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

        # Lookup maps keyed by RDF subject URI → model instance.
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

        # ── 1. CONTACT POINTS ─────────────────────────────────────────────────
        for record in raw_records['ContactPoint']:
            email = str_value(record, 'email')
            contact_page = str_value(record, 'contact_page')

            if not email and not contact_page:
                logger.warning(
                    'Skipping ContactPoint with no email or page: %s',
                    record.subject_uri,
                )
                continue

            label = email or contact_page or record.subject_uri
            report['fetched']['contact_points'].append(label)

            cp, created = ContactPoint.objects.using('fair_genomes_db').get_or_create(
                email=email,
                contact_page=contact_page,
            )
            report['saved']['contact_points']['created' if created else 'updated'].append(label)
            cp_by_uri[record.subject_uri] = cp

        # ── 2. AGENTS ─────────────────────────────────────────────────────────
        for record in raw_records['Agent']:
            name = str_value(record, 'name')
            if not name:
                logger.warning('Skipping Agent with no name: %s', record.subject_uri)
                continue

            contact_point = cp_by_uri.get(str_value(record, 'contact_point') or '')

            report['fetched']['agents'].append(name)
            agent, created = Agent.objects.using('fair_genomes_db').update_or_create(
                name=name,
                defaults={
                    'description': str_value(record, 'description') or '',
                    'contact_point': contact_point,
                },
            )
            report['saved']['agents']['created' if created else 'updated'].append(name)
            agent_by_name[name] = agent
            agent_by_uri[record.subject_uri] = agent

        # ── 3. CATALOGS ───────────────────────────────────────────────────────
        for record in raw_records['Catalog']:
            name = str_value(record, 'name')
            if not name:
                logger.warning('Skipping Catalog with no name: %s', record.subject_uri)
                continue

            publisher_agent = _resolve_related(
                str_value(record, 'publisher'),
                agent_by_uri,
                agent_by_name,
            )

            report['fetched']['catalogs'].append(name)
            catalog, created = Catalog.objects.using('fair_genomes_db').update_or_create(
                name=name,
                defaults={
                    'title': str_value(record, 'title') or '',
                    'description': str_value(record, 'description') or '',
                    'publisher': publisher_agent,
                    'applicable_legislation': str_value(record, 'applicable_legislation') or '',
                },
            )
            report['saved']['catalogs']['created' if created else 'updated'].append(name)
            catalog_by_name[name] = catalog
            catalog_by_uri[record.subject_uri] = catalog

        # ── 4. DATASETS ───────────────────────────────────────────────────────
        pending_source_refs: list[tuple[Dataset, str]] = []

        for record in raw_records['Dataset']:
            name = str_value(record, 'name')
            if not name:
                logger.warning('Skipping Dataset with no name: %s', record.subject_uri)
                continue

            report['fetched']['datasets'].append(name)

            hdab_ref = str_value(record, 'hdab')
            hdab = _resolve_related(hdab_ref, agent_by_uri, agent_by_name)
            cp_ref = str_value(record, 'contact_point')
            contact_point = cp_by_uri.get(cp_ref or '')

            if not hdab:
                logger.warning('Skipping Dataset "%s": hdab agent "%s" not found', name, hdab_ref)
                report['skipped'].setdefault('datasets', []).append(
                    {'name': name, 'reason': 'hdab agent not resolved'}
                )
                continue
            if not contact_point:
                logger.warning('Skipping Dataset "%s": contact_point "%s" not found', name, cp_ref)
                report['skipped'].setdefault('datasets', []).append(
                    {'name': name, 'reason': f'contact_point "{cp_ref}" not resolved'}
                )
                continue

            publisher = _resolve_related(
                str_value(record, 'publisher'), agent_by_uri, agent_by_name
            )
            creator = _resolve_related(str_value(record, 'creator'), agent_by_uri, agent_by_name)
            custodian = _resolve_related(
                str_value(record, 'custodian'),
                agent_by_uri,
                agent_by_name,
            )
            catalog = _resolve_related(
                str_value(record, 'catalog'), catalog_by_uri, catalog_by_name
            )
            source_ref = str_value(record, 'source')
            source = _resolve_related(source_ref, dataset_by_uri, dataset_by_name)

            defaults = {
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
                'publisher': publisher,
                'creator': creator,
                'custodian': custodian,
                'catalog': catalog,
                'source': source,
            }

            dataset, created = Dataset.objects.using('fair_genomes_db').update_or_create(
                name=name,
                defaults=defaults,
            )
            report['saved']['datasets']['created' if created else 'updated'].append(name)
            dataset_by_name[name] = dataset
            dataset_by_uri[record.subject_uri] = dataset

            if source_ref:
                pending_source_refs.append((dataset, source_ref))

        for dataset, source_ref in pending_source_refs:
            source = _resolve_related(source_ref, dataset_by_uri, dataset_by_name)
            if source is None or dataset.source_id == source.pk:
                continue
            dataset.source = source
            dataset.save(update_fields=['source'], using='fair_genomes_db')

        # ── 5. DISTRIBUTIONS ──────────────────────────────────────────────────
        for record in raw_records['Distribution']:
            name = str_value(record, 'name')
            if not name:
                logger.warning('Skipping Distribution with no name: %s', record.subject_uri)
                continue

            report['fetched']['distributions'].append(name)

            dataset_ref = str_value(record, 'dataset_name')
            dataset = _resolve_related(dataset_ref, dataset_by_uri, dataset_by_name)

            if not dataset:
                logger.warning(
                    'Skipping Distribution "%s": dataset "%s" not found', name, dataset_ref
                )
                report['skipped'].setdefault('distributions', []).append(
                    {'name': name, 'reason': f'dataset "{dataset_ref}" not resolved'}
                )
                continue

            defaults = {
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
            }

            _, created = Distribution.objects.using('fair_genomes_db').update_or_create(
                name=name,
                defaults=defaults,
            )
            report['saved']['distributions']['created' if created else 'updated'].append(name)

        # ── STALE-ENTITY CLEANUP ──────────────────────────────────────────────
        fetched_datasets = set(report['fetched']['datasets'])
        if fetched_datasets:
            deleted_ds, _ = (
                Dataset.objects.using('fair_genomes_db').exclude(name__in=fetched_datasets).delete()
            )
            if deleted_ds:
                logger.info('Removed %d stale Dataset(s) not present in current RDF', deleted_ds)
                report['deleted'] = report.get('deleted', {})
                report['deleted']['datasets'] = deleted_ds

        fetched_distributions = set(report['fetched']['distributions'])
        if fetched_distributions:
            deleted_dist, _ = (
                Distribution.objects.using('fair_genomes_db')
                .exclude(name__in=fetched_distributions)
                .delete()
            )
            if deleted_dist:
                logger.info(
                    'Removed %d stale Distribution(s) not present in current RDF', deleted_dist
                )
                report['deleted'] = report.get('deleted', {})
                report['deleted']['distributions'] = deleted_dist

        # ── OVERALL STATUS ────────────────────────────────────────────────────
        all_entity_types = ('contact_points', 'agents', 'catalogs', 'datasets', 'distributions')
        any_saved = any(
            report['saved'][ent][op] for ent in all_entity_types for op in ('created', 'updated')
        )
        any_skipped = bool(report['skipped'])
        if any_saved and not any_skipped:
            report['status'] = 'complete'
        elif any_saved:
            report['status'] = 'partial'
        else:
            report['status'] = 'nothing_saved'

        return report

    def _sync_stats(self) -> dict:
        """
        Fetch full value distributions from MOLGENIS for every active
        ``StatDefinition`` and write the results back to ``StatResult``.

        For each definition a GraphQL ``_groupBy`` aggregation query is
        executed, returning all distinct values with their counts.

        Runs *outside* any transaction — a failure for one stat definition is
        logged and counted but does not prevent the others from being stored.

        Returns a dict with keys:
            updated  — number of StatResult rows successfully written
            failed   — number of definitions that raised an error
            errors   — list of short error strings for reporting
        """
        from fair_genomes.models import StatDefinition

        definitions = (
            StatDefinition.objects.using('fair_genomes_db')
            .filter(is_active=True)
            .select_related('distribution')
        )
        updated = 0
        failed = 0
        errors: list[str] = []

        for defn in definitions:
            ok, err = self.sync_single_stat(defn.molgenis_table, defn.molgenis_column)
            if ok:
                updated += 1
            else:
                failed += 1
                errors.append(err)

        return {'updated': updated, 'failed': failed, 'errors': errors}

    def sync_single_stat(self, table: str, column: str) -> tuple[bool, str]:
        """
        Fetch a single _groupBy aggregation and persist the result.

        Returns ``(True, '')`` on success or ``(False, error_message)`` on failure.
        """
        from datetime import datetime

        from fair_genomes.models import StatResult

        table_cap = table[0].upper() + table[1:]
        # MOLGENIS EMX2 _groupBy does not accept a 'column' argument;
        # instead we request the column directly in the selection set.
        # Ref/ontology columns return objects — request { value }.
        # Scalar columns don't — if the first attempt errors, retry bare.
        query_ref = f'{{ {table_cap}_groupBy {{ count {column} {{ value }} }} }}'

        headers: dict[str, str] = {'Content-Type': 'application/json'}
        if self.api_token:
            headers['x-molgenis-token'] = self.api_token

        data = None
        queries = (query_ref, f'{{ {table_cap}_groupBy {{ count {column} }} }}')
        for attempt, query in enumerate(queries):
            is_last = attempt == len(queries) - 1
            try:
                response = requests.post(
                    self.graphql_url,
                    json={'query': query},
                    headers=headers,
                    timeout=self.timeout,
                )
                # A 400 on the first (ref) query means the column is a plain
                # scalar — fall through to the scalar retry instead of giving up.
                if response.status_code == 400 and not is_last:
                    continue
                response.raise_for_status()
                data = response.json()
            except (requests.RequestException, ValueError) as exc:
                msg = f'{table}.{column}: {exc}'
                logger.warning('Stat sync failed: %s', msg)
                return False, msg

            if 'errors' not in data:
                break  # success
            # If this was the ref query and the error looks like a sub-selection
            # issue, fall through to retry as scalar.

        if data and 'errors' in data:
            msg = f'{table}.{column}: GraphQL errors {data["errors"]}'
            logger.warning('Stat sync GraphQL error: %s', msg)
            return False, msg

        rows = data.get('data', {}).get(f'{table_cap}_groupBy', []) or []

        distribution: dict[str, int] = {}
        for row in rows:
            count = row.get('count', 0)
            # Ref / ontology columns nest the value under {column: {value: ...}}.
            # Scalar columns return the value directly.
            col_val = row.get(column)
            if isinstance(col_val, dict):
                value = col_val.get('value') or col_val.get('name') or col_val.get('label') or ''
            elif col_val is not None:
                value = str(col_val)
            else:
                value = ''
            if value:
                distribution[value] = count

        StatResult.objects.using('fair_genomes_db').update_or_create(
            table_name=table,
            column_name=column,
            defaults={
                'distribution': distribution,
                'last_synced': datetime.now(tz=UTC),
            },
        )
        return True, ''

    def introspect_molgenis_schema(self) -> dict[str, list[str]]:
        """
        Fetch the MOLGENIS GraphQL schema via introspection and return a
        mapping of ``{table_name: [column_name, ...]}``.

        Filters out internal types (``__``-prefixed, ``*_groupBy``, ``Query``,
        ``Mutation``, ``*_agg``, ``_meta``…).

        Returns an empty dict if the API URL is not configured or on error.
        """
        if not self.graphql_url:
            return {}

        query = '{ __schema { types { name kind fields { name } } } }'
        headers: dict[str, str] = {'Content-Type': 'application/json'}
        if self.api_token:
            headers['x-molgenis-token'] = self.api_token

        try:
            response = requests.post(
                self.graphql_url,
                json={'query': query},
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning('MOLGENIS schema introspection failed: %s', exc)
            return {}

        types = data.get('data', {}).get('__schema', {}).get('types', [])

        skip_suffixes = (
            '_groupBy',
            'GroupBy',
            '_agg',
            'Aggregate',
            '_aggregate',
            'Input',
            'OrderByInput',
            'FilterInput',
            'Connection',
            'Edge',
        )
        skip_prefixes = (
            '__',
            '_',
            'Molgenis',
            'Signin',
            'Save',
        )
        skip_names = {
            'Query',
            'Mutation',
            'Subscription',
            'String',
            'Int',
            'Float',
            'Boolean',
            'ID',
            'DateTime',
            'JSON',
        }

        result: dict[str, list[str]] = {}
        for t in types:
            name = t.get('name', '')
            kind = t.get('kind', '')
            if kind != 'OBJECT':
                continue
            if any(name.startswith(p) for p in skip_prefixes):
                continue
            if name in skip_names:
                continue
            if any(name.endswith(s) for s in skip_suffixes):
                continue
            # Exclude any type that contains Aggregate or GroupBy anywhere — these
            # are sub-types like ClinicalAggregate_avg, SequencingGroupBy__sum.
            if 'Aggregate' in name or 'GroupBy' in name:
                continue
            fields = [
                f['name']
                for f in (t.get('fields') or [])
                if not f['name'].startswith('_')
                and not f['name'].endswith('_agg')
                and not f['name'].endswith('_groupBy')
                and not f['name'].endswith('_aggregate')
                and 'mg_' not in f['name']
            ]
            if fields:
                result[name] = sorted(fields)

        return dict(sorted(result.items()))
