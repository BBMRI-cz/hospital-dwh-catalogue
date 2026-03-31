"""
Service layer for Fair Genomes catalogue.

Two sync sources contribute to one atomic transaction per run:

  1. RDF (FAIR Data Point) — configured via FAIR_GENOMES_RDF_URL.
       - Agent    : saved fully.
       - Catalog  : saved with partial data (applicable_legislation mandatory
                    in HealthDCAT-AP v6 but absent from FDP — stored as '').
       - Dataset  : collected but NOT saved (mandatory fields missing).

  2. GraphQL (MOLGENIS EMX2) — configured via FAIR_GENOMES_API_URL +
     FAIR_GENOMES_API_TOKEN.
       - Table    : DATA tables only (ONTOLOGIES lookup tables are skipped).
       - Column   : all columns belonging to the saved DATA tables.

Both sources' DB writes are wrapped in a single transaction.atomic so the
catalogue never has partial data — either everything succeeds or nothing is
persisted.

sync() returns a structured report dict for downstream reporting.
"""

import logging
import time
from datetime import UTC

import requests

from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)


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
        timeout: int = 30,
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
            graphql_url               — the GraphQL URL that was fetched (empty if not configured)
            fetched                   — names of RDF entities found per type
            saved                     — created/updated counts per entity type
            skipped                   — entities skipped due to unresolved FKs
            graphql_synced            — tables/columns created+updated counts
            graphql_filtered_out      — table names skipped (ONTOLOGIES)
            graphql_fields_not_in_model — GraphQL column fields that have no Column model field
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

        graphql_tables = None
        if self.graphql_url:
            graphql_tables = self._fetch_graphql_schema()
            logger.info('GraphQL schema fetched', extra={'table_count': len(graphql_tables)})

        # ── Phase 2: all DB writes in one atomic transaction ──────────────────
        _empty_counts: dict = {'created': [], 'updated': []}
        with transaction.atomic(using='fair_genomes_db'):
            report = (
                self._process_graph(graph)
                if graph
                else {
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
                        'contact_points': {**_empty_counts},
                        'agents': {**_empty_counts},
                        'catalogs': {**_empty_counts},
                        'datasets': {**_empty_counts},
                        'distributions': {**_empty_counts},
                    },
                    'skipped': {},
                }
            )

            if graphql_tables is not None:
                gql_report = self._process_graphql_tables(graphql_tables)
                report['graphql_url'] = self.graphql_url
                report['graphql_synced'] = gql_report['synced']
                report['graphql_filtered_out'] = gql_report['filtered_out']
                report['graphql_fields_not_in_model'] = gql_report['fields_not_in_model']
            else:
                report['graphql_url'] = ''
                report['graphql_synced'] = None
                report['graphql_filtered_out'] = []
                report['graphql_fields_not_in_model'] = []

        # ── Phase 3: stat counts — outside transaction so a failed count query
        # never rolls back the schema sync that just completed successfully.
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

    def _fetch(self, url: str) -> requests.Response:
        """HTTP GET with an RDF-friendly Accept header."""
        try:
            response = requests.get(
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
        """
        Walk the parsed RDF graph and persist all HealthDCAT-AP v6 entities.

        Processing order respects FK dependencies:
        ContactPoint → Agent → Catalog → Dataset → Distribution.
        """
        from datetime import datetime

        from rdflib import Literal, Namespace, URIRef
        from rdflib.namespace import DCAT, DCTERMS, FOAF, RDF, RDFS

        from fair_genomes.models import (
            Agent,
            Catalog,
            ContactPoint,
            Dataset,
            Distribution,
        )

        fdp_base = self.rdf_url.rstrip('/')
        FDP_O = Namespace('https://w3id.org/fdp/fdp-o#')
        HEALTHDCAT = Namespace('http://healthdcat-ap.eu/ns#')
        GEODCATAP = Namespace('http://data.europa.eu/930/')
        VCARD = Namespace('http://www.w3.org/2006/vcard/ns#')

        def col(entity: str, field: str) -> URIRef:
            """FDP column predicate URI for a given entity and field name."""
            return URIRef(f'{fdp_base}/{entity}/column/{field}')

        def get_literal(subject, *predicates) -> str | None:
            for pred in predicates:
                val = g.value(subject, pred)
                if isinstance(val, Literal):
                    return str(val)
            return None

        def get_uri(subject, *predicates) -> str | None:
            for pred in predicates:
                val = g.value(subject, pred)
                if isinstance(val, URIRef):
                    return str(val)
            return None

        def parse_datetime(val: str | None) -> datetime | None:
            if not val:
                return None
            try:
                return datetime.fromisoformat(val)
            except (ValueError, TypeError):
                return None

        def parse_int(val: str | None) -> int | None:
            if not val:
                return None
            try:
                return int(val)
            except (ValueError, TypeError):
                return None

        _ec: dict = {'created': [], 'updated': []}
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
                'contact_points': {**_ec},
                'agents': {**_ec},
                'catalogs': {**_ec},
                'datasets': {**_ec},
                'distributions': {**_ec},
            },
            'skipped': {},
        }

        # Lookup maps keyed by RDF subject URI → model instance.
        cp_by_uri: dict[str, ContactPoint] = {}
        agent_by_name: dict[str, Agent] = {}
        catalog_by_name: dict[str, Catalog] = {}
        dataset_by_name: dict[str, Dataset] = {}

        def _resolve_agent(name_val: str | None) -> Agent | None:
            if not name_val:
                return None
            return agent_by_name.get(name_val)

        def _resolve_cp(uri_val: str | None) -> ContactPoint | None:
            if not uri_val:
                return None
            return cp_by_uri.get(uri_val)

        # ── 1. CONTACT POINTS ─────────────────────────────────────────────────
        for subj in g.subjects(RDF.type, VCARD.Kind):
            email = get_literal(subj, VCARD.hasEmail, col('ContactPoint', 'email'))
            contact_page = get_literal(
                subj, VCARD.hasURL, col('ContactPoint', 'contact_page')
            ) or get_uri(subj, VCARD.hasURL, col('ContactPoint', 'contact_page'))

            if not email and not contact_page:
                logger.warning('Skipping ContactPoint with no email or page: %s', subj)
                continue

            label = email or contact_page or str(subj)
            report['fetched']['contact_points'].append(label)

            # Look up by the combination of fields — that's the natural identity.
            cp, created = ContactPoint.objects.using('fair_genomes_db').get_or_create(
                email=email,
                contact_page=contact_page,
            )
            report['saved']['contact_points']['created' if created else 'updated'].append(label)
            cp_by_uri[str(subj)] = cp

        # ── 2. AGENTS ─────────────────────────────────────────────────────────
        for subj in g.subjects(RDF.type, FOAF.Agent):
            name = get_literal(subj, FOAF.name, RDFS.label, col('Agent', 'name'))
            if not name:
                logger.warning('Skipping Agent with no name: %s', subj)
                continue

            description = get_literal(subj, DCTERMS.description, col('Agent', 'description'))
            cp_uri = get_uri(subj, DCAT.contactPoint, col('Agent', 'contactPoint'))
            contact_point = _resolve_cp(cp_uri)

            report['fetched']['agents'].append(name)
            _, created = Agent.objects.using('fair_genomes_db').update_or_create(
                name=name,
                defaults={
                    'description': description or '',
                    'contact_point': contact_point,
                },
            )
            report['saved']['agents']['created' if created else 'updated'].append(name)
            agent_by_name[name] = _

        # ── 3. CATALOGS ───────────────────────────────────────────────────────
        for subj in g.subjects(RDF.type, DCAT.Catalog):
            name = get_literal(subj, RDFS.label, col('Catalog', 'name'))
            if not name:
                logger.warning('Skipping Catalog with no name: %s', subj)
                continue

            title = get_literal(subj, DCTERMS.title, col('Catalog', 'title'))
            description = get_literal(subj, DCTERMS.description, col('Catalog', 'description'))
            applicable_legislation = (
                get_literal(subj, DCTERMS.relation, col('Catalog', 'applicable_legislation'))
                or get_uri(subj, DCTERMS.relation, col('Catalog', 'applicable_legislation'))
                or ''
            )
            publisher_name = get_literal(subj, DCTERMS.publisher, col('Catalog', 'publisher'))
            publisher_agent = _resolve_agent(publisher_name)

            report['fetched']['catalogs'].append(name)
            _, created = Catalog.objects.using('fair_genomes_db').update_or_create(
                name=name,
                defaults={
                    'title': title or '',
                    'description': description or '',
                    'publisher': publisher_agent,
                    'applicable_legislation': applicable_legislation,
                },
            )
            report['saved']['catalogs']['created' if created else 'updated'].append(name)
            catalog_by_name[name] = _

        # ── 4. DATASETS ───────────────────────────────────────────────────────
        for subj in g.subjects(RDF.type, DCAT.Dataset):
            name = get_literal(subj, RDFS.label, col('Dataset', 'name'))
            if not name:
                logger.warning('Skipping Dataset with no name: %s', subj)
                continue

            report['fetched']['datasets'].append(name)

            # Resolve mandatory non-nullable FKs.
            hdab_name = get_literal(subj, HEALTHDCAT.hdab, col('Dataset', 'hdab'))
            hdab = _resolve_agent(hdab_name)
            cp_uri = get_uri(subj, DCAT.contactPoint, col('Dataset', 'contactPoint'))
            contact_point = _resolve_cp(cp_uri)

            if not hdab:
                logger.warning('Skipping Dataset "%s": hdab agent "%s" not found', name, hdab_name)
                report['skipped'].setdefault('datasets', []).append(
                    {'name': name, 'reason': f'hdab agent "{hdab_name}" not resolved'}
                )
                continue
            if not contact_point:
                logger.warning('Skipping Dataset "%s": contact_point "%s" not found', name, cp_uri)
                report['skipped'].setdefault('datasets', []).append(
                    {'name': name, 'reason': f'contact_point "{cp_uri}" not resolved'}
                )
                continue

            # Optional FK fields.
            publisher_name = get_literal(subj, DCTERMS.publisher, col('Dataset', 'publisher'))
            creator_name = get_literal(subj, DCTERMS.creator, col('Dataset', 'creator'))
            custodian_name = get_literal(subj, GEODCATAP.custodian, col('Dataset', 'custodian'))
            catalog_name = get_literal(subj, col('Dataset', 'catalog'))
            source_name = get_literal(subj, DCTERMS.source, col('Dataset', 'source'))

            defaults = {
                'title': get_literal(subj, DCTERMS.title, col('Dataset', 'title')) or '',
                'version': get_literal(subj, DCTERMS.hasVersion, col('Dataset', 'version')) or '',
                'description': get_literal(subj, DCTERMS.description, col('Dataset', 'description'))
                or '',
                'identifier': get_literal(subj, DCTERMS.identifier, col('Dataset', 'identifier'))
                or str(subj),
                'type': get_literal(subj, DCTERMS.type, col('Dataset', 'type')) or '',
                'theme': get_literal(subj, DCAT.theme, col('Dataset', 'theme')) or '',
                'keyword': get_literal(subj, DCAT.keyword, col('Dataset', 'keyword')) or '',
                'provenance': get_literal(subj, DCTERMS.provenance, col('Dataset', 'provenance'))
                or '',
                'conforms_to': get_literal(subj, DCTERMS.conformsTo, col('Dataset', 'conformsTo'))
                or '',
                'access_rights': get_literal(
                    subj, DCTERMS.accessRights, col('Dataset', 'access_rights')
                )
                or get_uri(subj, DCTERMS.accessRights, col('Dataset', 'access_rights'))
                or '',
                'applicable_legislation': get_literal(
                    subj, DCTERMS.relation, col('Dataset', 'applicable_legislation')
                )
                or get_uri(subj, DCTERMS.relation, col('Dataset', 'applicable_legislation'))
                or '',
                'health_category': get_literal(
                    subj, HEALTHDCAT.healthCategory, col('Dataset', 'health_category')
                )
                or get_uri(subj, HEALTHDCAT.healthCategory, col('Dataset', 'health_category'))
                or '',
                'issued': parse_datetime(get_literal(subj, DCTERMS.issued, FDP_O.metadataIssued)),
                'modified': parse_datetime(
                    get_literal(subj, DCTERMS.modified, FDP_O.metadataModified)
                ),
                'hdab': hdab,
                'contact_point': contact_point,
                'publisher': _resolve_agent(publisher_name),
                'creator': _resolve_agent(creator_name),
                'custodian': _resolve_agent(custodian_name),
                'catalog': catalog_by_name.get(catalog_name) if catalog_name else None,
                'source': dataset_by_name.get(source_name) if source_name else None,
            }

            _, created = Dataset.objects.using('fair_genomes_db').update_or_create(
                name=name,
                defaults=defaults,
            )
            report['saved']['datasets']['created' if created else 'updated'].append(name)
            dataset_by_name[name] = _

        # ── 5. DISTRIBUTIONS ──────────────────────────────────────────────────
        for subj in g.subjects(RDF.type, DCAT.Distribution):
            name = get_literal(subj, RDFS.label, col('Distribution', 'name'))
            if not name:
                logger.warning('Skipping Distribution with no name: %s', subj)
                continue

            report['fetched']['distributions'].append(name)

            ds_name = get_literal(subj, col('Distribution', 'dataset_name'))
            dataset = dataset_by_name.get(ds_name) if ds_name else None
            if not dataset:
                # Try resolving via dcat:Distribution being a child of dcat:Dataset.
                ds_uri = get_uri(subj, DCTERMS.isPartOf)
                if ds_uri:
                    ds_label = get_literal(g.resource(URIRef(ds_uri)).identifier, RDFS.label)
                    dataset = dataset_by_name.get(ds_label) if ds_label else None

            if not dataset:
                logger.warning('Skipping Distribution "%s": dataset "%s" not found', name, ds_name)
                report['skipped'].setdefault('distributions', []).append(
                    {'name': name, 'reason': f'dataset "{ds_name}" not resolved'}
                )
                continue

            defaults = {
                'dataset_name': dataset,
                'title': get_literal(subj, DCTERMS.title, col('Distribution', 'title')) or '',
                'description': get_literal(
                    subj, DCTERMS.description, col('Distribution', 'description')
                )
                or '',
                'format': get_literal(subj, DCTERMS.format, col('Distribution', 'format')) or '',
                'conforms_to': get_literal(
                    subj, DCTERMS.conformsTo, col('Distribution', 'conforms_to')
                )
                or '',
                'byte_size': parse_int(
                    get_literal(subj, DCAT.byteSize, col('Distribution', 'byte_size'))
                ),
                'rights': get_literal(subj, DCTERMS.rights, col('Distribution', 'rights')) or '',
                'release_date': parse_datetime(
                    get_literal(subj, DCTERMS.issued, col('Distribution', 'release_date'))
                ),
                'modification_date': parse_datetime(
                    get_literal(subj, DCTERMS.modified, col('Distribution', 'modification_date'))
                ),
                'access_url': get_literal(subj, DCAT.accessURL, col('Distribution', 'access_url'))
                or get_uri(subj, DCAT.accessURL, col('Distribution', 'access_url'))
                or '',
                'applicable_legislation': get_literal(
                    subj, DCTERMS.relation, col('Distribution', 'applicable_legislation')
                )
                or get_uri(subj, DCTERMS.relation, col('Distribution', 'applicable_legislation'))
                or '',
                'licence': get_literal(subj, DCTERMS.license, col('Distribution', 'licence'))
                or get_uri(subj, DCTERMS.license, col('Distribution', 'licence'))
                or '',
            }

            _, created = Distribution.objects.using('fair_genomes_db').update_or_create(
                name=name,
                defaults=defaults,
            )
            report['saved']['distributions']['created' if created else 'updated'].append(name)

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

    def _fetch_graphql_schema(self) -> list[dict]:
        """
        POST to the MOLGENIS EMX2 GraphQL endpoint and return the raw list of
        table dicts from ``data._schema.tables``.

        Authentication is via the ``x-molgenis-token`` request header, read
        from FAIR_GENOMES_API_TOKEN.

        Raises FairGenomesAPIException on any network, HTTP, or GraphQL error.
        """
        query = (
            '{ _schema { tables { name label description tableType semantics '
            'columns { name label description columnType semantics } } } }'
        )
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
        except requests.RequestException as exc:
            raise FairGenomesAPIException(
                f'Failed to fetch GraphQL schema from {self.graphql_url}: {exc}'
            ) from exc
        except ValueError as exc:
            raise FairGenomesAPIException(
                f'Invalid JSON response from {self.graphql_url}: {exc}'
            ) from exc

        if 'errors' in data:
            raise FairGenomesAPIException(
                f'GraphQL errors from {self.graphql_url}: {data["errors"]}'
            )

        tables = data.get('data', {}).get('_schema', {}).get('tables', [])
        if tables is None:
            raise FairGenomesAPIException(
                f'No "_schema.tables" key in GraphQL response from {self.graphql_url}'
            )
        return tables

    def _process_graphql_tables(self, tables: list[dict]) -> dict:
        """
        Persist Table and Column records from a MOLGENIS GraphQL schema response.

        Only tables with ``tableType == "DATA"`` are saved; ONTOLOGIES lookup
        tables are recorded in the ``filtered_out`` list and skipped.

        Column PKs are stored as ``"{table_name}.{column_name}"`` to guarantee
        uniqueness across all tables.

        Must be called inside a ``transaction.atomic`` block (sync() ensures this).
        """
        from fair_genomes.models import Column, Table

        # GraphQL fields present in the schema response that have no matching
        # field on the Column model.
        fields_not_in_model = ['refTable', 'required', 'readonly', 'key']

        data_tables = [t for t in tables if t.get('tableType') == 'DATA']
        filtered_out = [t['name'] for t in tables if t.get('tableType') != 'DATA' and t.get('name')]

        synced_tables: dict[str, list[str]] = {'created': [], 'updated': []}
        synced_columns: dict[str, int] = {'created': 0, 'updated': 0}

        # Derive a stable base URL for the ``url`` field (mandatory, non-nullable).
        # Use the first semantic IRI if present, otherwise build from the endpoint.
        base_url = (
            self.graphql_url.split('/graphql')[0]
            if '/graphql' in self.graphql_url
            else self.graphql_url
        )

        # Ensure every synced table has a browseable Distribution → Dataset chain.
        auto_distribution = self._ensure_fg_distribution(base_url)

        for table_data in data_tables:
            table_name = table_data.get('name', '').strip()
            if not table_name:
                logger.warning('Skipping GraphQL table with empty name')
                continue

            semantics: list[str] = table_data.get('semantics') or []
            url = semantics[0] if semantics else f'{base_url}/tables/{table_name}'

            _, created = Table.objects.using('fair_genomes_db').update_or_create(
                name=table_name,
                defaults={
                    'title': table_data.get('label') or '',
                    'description': table_data.get('description') or '',
                    'url': url,
                    'distribution': auto_distribution,
                },
            )
            synced_tables['created' if created else 'updated'].append(table_name)

            for col_data in table_data.get('columns') or []:
                col_name = col_data.get('name', '').strip()
                if not col_name:
                    continue

                col_pk = f'{table_name}.{col_name}'
                col_semantics: list[str] = col_data.get('semantics') or []
                prop_url = col_semantics[0] if col_semantics else None

                _, col_created = Column.objects.using('fair_genomes_db').update_or_create(
                    name=col_pk,
                    defaults={
                        'table_id': table_name,
                        'title': col_data.get('label') or col_name,
                        'description': col_data.get('description') or '',
                        'datatype': col_data.get('columnType') or '',
                        'property_url': prop_url,
                    },
                )
                if col_created:
                    synced_columns['created'] += 1
                else:
                    synced_columns['updated'] += 1

        return {
            'synced': {
                'tables': synced_tables,
                'columns': synced_columns,
            },
            'filtered_out': filtered_out,
            'fields_not_in_model': fields_not_in_model,
            'auto_distribution': auto_distribution.name if auto_distribution else None,
        }

    def _ensure_fg_distribution(self, base_url: str):
        """
        Get or create a minimal ContactPoint → Agent → Dataset → Distribution
        chain so that GraphQL-synced Tables always have a browseable entry
        point in the catalogue.

        Uses ``get_or_create`` throughout so re-running sync is idempotent.
        """
        from fair_genomes.models import Agent, ContactPoint, Dataset, Distribution

        cp, _ = ContactPoint.objects.using('fair_genomes_db').get_or_create(
            contact_page=base_url,
            defaults={'email': None},
        )

        agent, _ = Agent.objects.using('fair_genomes_db').get_or_create(
            name='FAIR_GENOMES_AUTO',
            defaults={'contact_point': cp, 'description': 'Auto-created by GraphQL sync'},
        )

        dataset, _ = Dataset.objects.using('fair_genomes_db').get_or_create(
            name='DS_FAIR_GENOMES_AUTO',
            defaults={
                'identifier': base_url,
                'title': 'FAIR Genomes (auto)',
                'description': 'Auto-created placeholder dataset — synced from MOLGENIS FAIR Genomes API.',
                'type': 'http://publications.europa.eu/resource/authority/dataset-type/SENSITIVE',
                'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                'keyword': 'fair-genomes,genomics',
                'provenance': f'Synced from MOLGENIS FAIR Genomes API at {base_url}',
                'contact_point': cp,
                'access_rights': 'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC',
                'applicable_legislation': 'http://data.europa.eu/eli/reg/2016/679/oj',
                'health_category': 'patient_data',
                'hdab': agent,
                'publisher': agent,
            },
        )

        distribution, _ = Distribution.objects.using('fair_genomes_db').get_or_create(
            name='DIST_FAIR_GENOMES_AUTO',
            defaults={
                'dataset_name': dataset,
                'title': 'FAIR Genomes MOLGENIS API (auto)',
                'access_url': base_url,
                'applicable_legislation': 'http://data.europa.eu/eli/reg/2016/679/oj',
            },
        )

        logger.info(
            'Auto-distribution ensured: %s (dataset: %s)',
            distribution.name,
            dataset.name,
        )
        return distribution

    def _sync_stats(self) -> dict:
        """
        Fetch counts from MOLGENIS for every definition in ``stat_config`` and
        write the results back to ``StatResult``.

        Runs *outside* any transaction — a failure for one stat definition is
        logged and counted but does not prevent the others from being stored.

        Returns a dict with keys:
            updated  — number of StatResult rows successfully written
            failed   — number of definitions that raised an error
            errors   — list of short error strings for reporting
        """
        from datetime import datetime

        from fair_genomes.models import StatResult
        from fair_genomes.stat_config import get_stat_definitions

        definitions = get_stat_definitions()
        updated = 0
        failed = 0
        errors: list[str] = []

        for defn in definitions:
            # Build the GraphQL filter expression based on column type.
            # ref / ref_array columns store their value in a nested ontology
            # object, so the filter must go one level deeper.
            # Accept both lowercase ('ref') from stat_config and uppercase
            # ('REF') as stored by the API / Column.datatype field.
            if defn.column_type.upper() in ('REF', 'REF_ARRAY'):
                filter_expr = (
                    f'{{ {defn.column}: {{ value: {{ equals: "{defn.filter_value}" }} }} }}'
                )
            else:
                filter_expr = f'{{ {defn.column}: {{ equals: "{defn.filter_value}" }} }}'

            query = f'{{ {defn.table.capitalize()}_agg(filter: {filter_expr}) {{ count }} }}'

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
                msg = f'{defn.table}.{defn.column}={defn.filter_value!r}: {exc}'
                logger.warning('Stat sync failed: %s', msg)
                errors.append(msg)
                failed += 1
                continue

            if 'errors' in data:
                msg = f'{defn.table}.{defn.column}={defn.filter_value!r}: GraphQL errors {data["errors"]}'
                logger.warning('Stat sync GraphQL error: %s', msg)
                errors.append(msg)
                failed += 1
                continue

            count = data.get('data', {}).get(f'{defn.table.capitalize()}_agg', {}).get('count')

            StatResult.objects.using('fair_genomes_db').update_or_create(
                table_name=defn.table,
                column_name=defn.column,
                filter_value=defn.filter_value,
                defaults={
                    'count': count,
                    'last_synced': datetime.now(tz=UTC),
                },
            )
            updated += 1

        return {'updated': updated, 'failed': failed, 'errors': errors}
