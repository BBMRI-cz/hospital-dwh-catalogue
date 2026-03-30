"""
Shared JSON-LD export utilities for HealthDCAT-AP datasets.

Extracted from warehouse/views.py so that both warehouse and fair_genomes
can produce identical JSON-LD output without duplicating logic.

Public API:
  build_jsonld(ds_dict)      — turns a serialised dataset dict into a JSON-LD document
  has_distributions(ds_dict) — returns False when a dataset has no distributions
"""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


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


def build_jsonld(ds_dict: dict) -> dict:
    """Build a Health DCAT-AP JSON-LD document from a serialised dataset dict.

    Changes vs. the original warehouse helper:
    * @context is loaded from the HealthDCAT-AP SHACL TTL via the schema
      registry instead of being hardcoded (falls back to _EXTRA_PREFIXES).
    * Contact-point email is emitted as a ``mailto:`` URI (vcard:hasEmail, Change 1).
    * ``geodcatap:custodian`` is emitted when present (Change 5).
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

    result: dict = {
        '@context': _build_context(),
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
            {
                '@type': ['dcat:Distribution', 'healthdcatap:HealthDistribution'],
                '@id': f'{base}/distribution/{d["name"]}',
                'dct:title': [{'@language': 'cs', '@value': d['title']}],
                'dcat:accessURL': {'@id': d.get('access_url') or ''},
                'dct:format': d.get('format') or '',
                'dcatap:applicableLegislation': {'@id': d.get('applicable_legislation') or ''},
                **({'healthdcatap:dbLayer': d['db_layer']} if d.get('db_layer') else {}),
            }
            for d in ds_dict.get('distributions', [])
        ],
    }

    if contact_email_iri:
        result['dcat:contactPoint'] = {
            '@type': 'vcard:Kind',
            'vcard:hasEmail': {'@id': contact_email_iri},
        }

    if custodian_name:
        result['geodcatap:custodian'] = {
            '@type': 'foaf:Agent',
            'foaf:name': custodian_name,
        }

    return result


def has_distributions(ds_dict: dict) -> bool:
    """Return True if the serialised dataset dict contains at least one distribution."""
    return bool(ds_dict.get('distributions'))
