"""
Service layer for Fair Genomes catalogue.

Syncs catalogue metadata from a FAIR Data Point (FDP) endpoint that exposes
RDF data.  The endpoint URL is configured via the FAIR_GENOMES_RDF_URL
environment variable.

Data parsed and saved:
  - Agent    : saved fully (name only; description/contact_point are absent in
               the FDP schema and are nullable in our model).
  - Catalog  : saved with partial data (applicable_legislation is mandatory in
               HealthDCAT-AP v6 but not present in the FDP — saved as empty
               string; must be filled in manually or via a second sync phase).
  - Dataset  : collected but NOT saved — several mandatory fields (hdab, type,
               access_rights, applicable_legislation, health_category) are
               absent from the FDP data.  See the sync report for details.

The sync() method returns a structured report dict suitable for downstream
reporting (management command, admin UI, log entries, etc.).
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class FairGenomesAPIException(Exception):
    """Raised when the FDP endpoint cannot be reached or its data cannot be parsed."""

    pass


class FairGenomesService:
    """Sync Fair Genomes catalogue data from a FAIR Data Point RDF endpoint."""

    def __init__(
        self,
        rdf_url: str | None = None,
        api_url: str | None = None,   # kept for backward compatibility
        api_token: str | None = None,  # kept for backward compatibility
        timeout: int = 30,
    ):
        self.rdf_url = rdf_url or getattr(settings, 'FAIR_GENOMES_RDF_URL', '')
        self.api_url = api_url or getattr(settings, 'FAIR_GENOMES_API_URL', '')
        self.api_token = api_token or getattr(settings, 'FAIR_GENOMES_API_TOKEN', '')
        self.timeout = timeout

    # ─────────────────────────────────────────────────────────────────────────
    # Public interface
    # ─────────────────────────────────────────────────────────────────────────

    def sync(self) -> dict:
        """
        Fetch RDF from the configured FDP endpoint, parse it, and save what is
        saveable to fair_genomes_db.

        Returns a structured report dict with the following top-level keys:
            status               — 'complete' | 'partial' | 'nothing_saved' | 'skipped'
            rdf_url              — the URL that was fetched
            fetched              — names of entities found in the RDF
            saved                — created/updated counts per entity type
            not_saved            — datasets that could not be saved and why
            partial_saves        — catalog fields saved with incomplete data
            rdf_fields_not_in_model — RDF fields that have no model equivalent
            model_fields_not_in_rdf — model fields absent from the RDF

        Raises:
            FairGenomesAPIException: if the HTTP request or RDF parsing fails.
        """
        if not self.rdf_url:
            return {
                'status': 'skipped',
                'reason': 'FAIR_GENOMES_RDF_URL is not configured — set it in the environment',
            }

        response = self._fetch(self.rdf_url)
        rdf_format = self._detect_format(response)

        try:
            from rdflib import Graph  # rdflib>=7.0.0 is in requirements.txt
            g = Graph()
            g.parse(data=response.text, format=rdf_format)
        except Exception as exc:
            raise FairGenomesAPIException(
                f'Failed to parse RDF from {self.rdf_url}: {exc}'
            ) from exc

        return self._process_graph(g)

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
            raise FairGenomesAPIException(
                f'Failed to fetch RDF from {url}: {exc}'
            ) from exc
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
        """Walk the parsed RDF graph and produce a structured sync report."""
        from rdflib import Literal, Namespace, URIRef
        from rdflib.namespace import DCAT, DCTERMS, FOAF, RDFS, RDF

        # The FDP encodes each field twice: once with a standard predicate
        # (e.g. dcterms:title) and once with a column-specific predicate
        # (e.g. <{fdp_base}/Dataset/column/title>).  Standard predicates
        # are used where available; column predicates are the fallback for
        # fields stored only via relative-URI predicates (<dct:source> etc.).
        fdp_base = self.rdf_url.rstrip('/')
        FDP_O = Namespace('https://w3id.org/fdp/fdp-o#')

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

        report: dict = {
            'status': 'partial',
            'rdf_url': self.rdf_url,
            'fetched': {'agents': [], 'catalogs': [], 'datasets': []},
            'saved': {
                'agents': {'created': [], 'updated': []},
                'catalogs': {'created': [], 'updated': []},
            },
            'not_saved': {'datasets': []},
            'partial_saves': {'catalogs': {}},
            'rdf_fields_not_in_model': {
                'Dataset': [
                    'license (dcterms:license) — Dataset model has no license field; '
                    'Distribution has licence',
                    'rightsHolder (dct:rightsHolder) — no direct field mapping in any '
                    'Dataset or Distribution model',
                ],
                'Agent': [
                    'mg_draft — MOLGENIS internal metadata, not catalogued',
                    'mg_insertedOn — MOLGENIS internal metadata, not catalogued',
                    'mg_updatedOn — MOLGENIS internal metadata, not catalogued',
                ],
                'Catalog': [
                    'mg_draft — MOLGENIS internal metadata, not catalogued',
                    'mg_insertedOn — MOLGENIS internal metadata, not catalogued',
                    'mg_updatedOn — MOLGENIS internal metadata, not catalogued',
                ],
            },
            'model_fields_not_in_rdf': {
                'Dataset': [
                    'hdab (non-nullable FK to Agent)',
                    'type',
                    'access_rights',
                    'applicable_legislation',
                    'health_category',
                ],
                'Catalog': ['applicable_legislation'],
                'Agent': ['description', 'contact_point'],
            },
        }

        # Import here to keep the class importable without Django setup
        from fair_genomes.models import Agent, Catalog

        # ── AGENTS ────────────────────────────────────────────────────────────
        for subj in g.subjects(RDF.type, FOAF.Agent):
            name = get_literal(subj, FOAF.name, RDFS.label, col('Agent', 'name'))
            if not name:
                logger.warning('Skipping Agent with no name: %s', subj)
                continue

            report['fetched']['agents'].append(name)
            _, created = Agent.objects.using('fair_genomes_db').update_or_create(
                name=name,
                defaults={},
            )
            report['saved']['agents']['created' if created else 'updated'].append(name)

        # ── CATALOGS ──────────────────────────────────────────────────────────
        for subj in g.subjects(RDF.type, DCAT.Catalog):
            name = get_literal(subj, RDFS.label, col('Catalog', 'name'))
            if not name:
                logger.warning('Skipping Catalog with no name: %s', subj)
                continue

            title = get_literal(subj, DCTERMS.title, col('Catalog', 'title'))
            description = get_literal(subj, DCTERMS.description, col('Catalog', 'description'))
            publisher_uri = get_uri(subj, DCTERMS.publisher, col('Catalog', 'publisher'))

            publisher_agent = None
            if publisher_uri and 'name=' in publisher_uri:
                publisher_name = publisher_uri.split('name=')[-1]
                try:
                    publisher_agent = Agent.objects.using('fair_genomes_db').get(
                        name=publisher_name
                    )
                except Agent.DoesNotExist:
                    logger.warning(
                        'Publisher Agent "%s" not found for Catalog "%s"',
                        publisher_name,
                        name,
                    )

            partial_notes: list[str] = [
                'applicable_legislation — mandatory in HealthDCAT-AP v6 but not present in RDF; '
                'saved as empty string',
            ]
            if not title:
                partial_notes.append('title — not present in RDF, saved as empty string')
            if not description:
                partial_notes.append('description — not present in RDF, saved as empty string')

            report['fetched']['catalogs'].append(name)
            _, created = Catalog.objects.using('fair_genomes_db').update_or_create(
                name=name,
                defaults={
                    'title': title or '',
                    'description': description or '',
                    'publisher': publisher_agent,
                    'applicable_legislation': '',
                },
            )
            report['saved']['catalogs']['created' if created else 'updated'].append(name)
            report['partial_saves']['catalogs'][name] = partial_notes

        # ── DATASETS (collected, not saved) ───────────────────────────────────
        for subj in g.subjects(RDF.type, DCAT.Dataset):
            name = get_literal(subj, RDFS.label, col('Dataset', 'name'))
            if not name:
                continue

            report['fetched']['datasets'].append(name)

            available: dict[str, str] = {'name': name}
            # Each entry: (report_key, predicate1, predicate2, ...)
            field_map = [
                ('title', DCTERMS.title, col('Dataset', 'title')),
                ('version', DCTERMS.hasVersion, col('Dataset', 'version')),
                ('description', DCTERMS.description, col('Dataset', 'description')),
                ('theme', DCAT.theme, col('Dataset', 'theme')),
                # RDF column is named "conformedTo"; model field is conforms_to
                ('conforms_to [RDF: conformedTo]', DCTERMS.conformsTo, col('Dataset', 'conformedTo')),
                ('keyword', DCAT.keyword, col('Dataset', 'keyword')),
                ('source', col('Dataset', 'source')),
                ('creator', col('Dataset', 'creator')),
                ('provenance', col('Dataset', 'provenance')),
                ('issued', FDP_O.metadataIssued, col('Dataset', 'issued')),
                ('modified', FDP_O.metadataModified, col('Dataset', 'modified')),
                ('contact_point_raw (email string)', DCAT.contactPoint, col('Dataset', 'contactPoint')),
                ('publisher (URI)', DCTERMS.publisher, col('Dataset', 'publisher')),
            ]
            for entry in field_map:
                key, *preds = entry
                val = get_literal(subj, *preds) or get_uri(subj, *preds)
                if val:
                    available[key] = val

            # Track RDF fields that exist in this record but have no model equivalent
            rdf_not_in_model: dict[str, str] = {}
            license_val = get_literal(subj, DCTERMS.license, col('Dataset', 'license'))
            if license_val:
                rdf_not_in_model['license'] = license_val
            rights_holder_val = get_literal(subj, col('Dataset', 'rightsHolder'))
            if rights_holder_val:
                rdf_not_in_model['rightsHolder'] = rights_holder_val

            report['not_saved']['datasets'].append({
                'name': name,
                'reason': 'missing required fields — cannot save without them',
                'missing_required': [
                    'hdab — non-nullable FK to Agent, not present in RDF',
                    'type — not present in RDF',
                    'access_rights — not present in RDF',
                    'applicable_legislation — not present in RDF',
                    'health_category — not present in RDF',
                ],
                'available_fields': list(available.keys()),
                'rdf_fields_not_in_model': rdf_not_in_model,
            })

        # ── OVERALL STATUS ────────────────────────────────────────────────────
        any_saved = any(
            report['saved'][ent][op]
            for ent in ('agents', 'catalogs')
            for op in ('created', 'updated')
        )
        if any_saved and not report['not_saved']['datasets']:
            report['status'] = 'complete'
        elif any_saved:
            report['status'] = 'partial'
        else:
            report['status'] = 'nothing_saved'

        return report
