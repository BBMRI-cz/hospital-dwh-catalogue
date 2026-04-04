"""
Shared JSON-LD / RDF export utilities for HealthDCAT-AP datasets.

Extracted from warehouse/views.py so that both warehouse and fair_genomes
can produce identical JSON-LD output without duplicating logic.

Public API:
  build_jsonld(ds_dict)      — turns a serialised dataset dict into a JSON-LD document
  build_turtle(ds_dict)      — turns a serialised dataset dict into Turtle (text/turtle)
  has_distributions(ds_dict) — returns False when a dataset has no distributions
"""

from __future__ import annotations

import json
import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)

# Matches a CURIE like ``dcat:Dataset`` or ``dct:title`` but NOT a full URI
# (which contains ``://``).  Group 1 is the prefix name.
_CURIE_RE = re.compile(r'^([A-Za-z][A-Za-z0-9_-]*):[^/]')


def _collect_used_prefixes(obj: object, prefixes: set[str]) -> None:
    """Recursively walk *obj* and add every CURIE prefix found to *prefixes*."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if not key.startswith('@'):
                m = _CURIE_RE.match(key)
                if m:
                    prefixes.add(m.group(1))
            _collect_used_prefixes(value, prefixes)
    elif isinstance(obj, list):
        for item in obj:
            _collect_used_prefixes(item, prefixes)
    elif isinstance(obj, str) and not obj.startswith('@'):
        m = _CURIE_RE.match(obj)
        if m:
            prefixes.add(m.group(1))


def _build_context() -> dict[str, str]:
    """
    Build the JSON-LD @context prefix map.

    Loads namespace prefixes from the HealthDCAT-AP SHACL shape files via the
    schema registry (base ``shacl/dcat-ap-SHACL.ttl`` + HealthDCAT-AP specific
    ``html/shacl/public-shapes.ttl``), so the map stays in sync with whatever
    version of the submodule is checked out.

    Falls back gracefully to an empty dict if the registry is unavailable
    (submodule absent, rdflib not installed, etc.).
    """
    try:
        from schema_registry.services import get_context_prefixes

        return get_context_prefixes()
    except Exception:
        logger.warning(
            'Could not load JSON-LD context prefixes from schema registry', exc_info=True
        )
        return {}


# ── CSVW / distribution helpers ──────────────────────────────────────────────


def _build_column(col: dict) -> dict:
    """Build a ``csvw:Column`` node from a column dict."""
    node: dict = {
        '@type': 'csvw:Column',
        'csvw:name': col['name'],
        'csvw:titles': col.get('title') or col['name'],
        'csvw:datatype': col.get('datatype') or '',
        'dct:description': col.get('description') or '',
    }
    if col.get('property_url'):
        node['csvw:propertyUrl'] = {'@id': col['property_url']}
    return node


def _build_table(table: dict) -> dict:
    """Build a ``csvw:Table`` node from a table dict."""
    node: dict = {
        '@type': 'csvw:Table',
        'dct:title': table.get('title') or table['name'],
    }
    if table.get('url'):
        node['csvw:url'] = {'@id': table['url']}
    columns = table.get('columns', [])
    if columns:
        node['csvw:column'] = [_build_column(c) for c in columns]
    return node


def _build_table_group(tables: list[dict]) -> dict:
    """Build a ``csvw:TableGroup`` node from a list of table dicts."""
    return {
        '@type': 'csvw:TableGroup',
        'csvw:table': [_build_table(t) for t in tables],
    }


def _build_distribution(d: dict, base: str) -> dict:
    """Build a single ``dcat:Distribution`` node, optionally with CSVW tables."""
    node: dict = {
        '@type': ['dcat:Distribution', 'healthdcatap:HealthDistribution'],
        '@id': f'{base}/distribution/{d["name"]}',
        'dct:title': [{'@language': 'cs', '@value': d['title']}],
        'dcat:accessURL': {'@id': d.get('access_url') or ''},
        'dct:format': d.get('format') or '',
        'dcatap:applicableLegislation': {'@id': d.get('applicable_legislation') or ''},
    }
    if d.get('db_layer'):
        node['healthdcatap:dbLayer'] = d['db_layer']
    tables = d.get('tables', [])
    if tables:
        node['adms:sample'] = _build_table_group(tables)
    return node


def build_jsonld(ds_dict: dict) -> dict:
    """Build a Health DCAT-AP JSON-LD document from a serialised dataset dict.

    Changes vs. the original warehouse helper:
    * @context is loaded from the HealthDCAT-AP SHACL TTL via the schema
      registry instead of being hardcoded (falls back to _EXTRA_PREFIXES).
    * Contact-point email is emitted as a ``mailto:`` URI (vcard:hasEmail, Change 1).
    * ``geodcatap:custodian`` is emitted when present (Change 5).
    * Distributions with tables emit a ``csvw:TableGroup`` / ``csvw:Table`` /
      ``csvw:Column`` hierarchy following the HealthDCAT-AP ``adms:sample`` pattern.
    """
    base = settings.SITE_URL.rstrip('/')

    # Normalise contact-point email to mailto: URI for RDF export (Change 1).
    raw_email = ds_dict.get('contact_point') or ''
    contact_email_iri = (
        (raw_email if raw_email.startswith('mailto:') else f'mailto:{raw_email}')
        if raw_email
        else ''
    )

    custodian_name = ds_dict.get('custodian')

    body: dict = {
        '@type': ['dcat:Dataset', 'healthdcatap:HealthDataset'],
        '@id': f'{base}/dataset/{ds_dict["app"]}/{ds_dict["name"]}',
        'dct:title': [{'@language': 'cs', '@value': ds_dict['title']}],
        'dct:description': [{'@language': 'cs', '@value': ds_dict.get('description') or ''}],
        'dcat:keyword': ds_dict.get('keywords', []),
        'dct:rightsHolder': {
            '@type': 'org:Organization',
            'foaf:name': ds_dict.get('custodian') or '',
        },
        'dct:publisher': {'@type': 'org:Organization', 'foaf:name': ds_dict.get('publisher') or ''},
        'dct:accessRights': {'@id': ds_dict.get('access_rights') or ''},
        'healthdcatap:hasHealthCategory': {'@id': ds_dict.get('health_category') or ''},
        'dcatap:applicableLegislation': {'@id': ds_dict.get('applicable_legislation') or ''},
        'dcat:distribution': [
            _build_distribution(d, base) for d in ds_dict.get('distributions', [])
        ],
    }

    if contact_email_iri:
        body['dcat:contactPoint'] = {
            '@type': 'vcard:Kind',
            'vcard:hasEmail': {'@id': contact_email_iri},
        }

    if custodian_name:
        body['geodcatap:custodian'] = {
            '@type': 'foaf:Agent',
            'foaf:name': custodian_name,
        }

    # Build @context with only the prefixes actually used in this document.
    used: set[str] = set()
    _collect_used_prefixes(body, used)
    full_context = _build_context()
    context = {k: v for k, v in full_context.items() if k in used}
    # Set @base so relative URIs resolve against SITE_URL (not file://).
    context['@base'] = f'{base}/'

    return {'@context': context, **body}


def has_distributions(ds_dict: dict) -> bool:
    """Return True if the serialised dataset dict contains at least one distribution."""
    return bool(ds_dict.get('distributions'))


def build_turtle(ds_dict: dict) -> str:
    """Build a HealthDCAT-AP Turtle serialisation from a serialised dataset dict.

    Uses rdflib to convert the JSON-LD document produced by ``build_jsonld``
    to Turtle format.  Returns a UTF-8 string.
    """
    from rdflib import Graph  # type: ignore[import-untyped]

    jsonld = build_jsonld(ds_dict)
    g = Graph()
    g.parse(data=json.dumps(jsonld), format='json-ld')
    return g.serialize(format='turtle')
