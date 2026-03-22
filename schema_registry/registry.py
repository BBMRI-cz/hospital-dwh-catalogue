"""
HealthDCAT-AP Schema Registry — in-memory loader
==================================================

Parses the SHACL TTL and HealthDCAT-AP cardinality rules from the
``health_dcat_ap/`` git submodule and returns a plain dict keyed by
prefixed semantics string (e.g. ``"dct:title"``).

The dict is loaded once per Python process (lazy singleton) and cached in
``_registry_cache``.  Call ``invalidate_cache()`` in tests to force a reload.

Returned dict shape (matches what the JS schema modal consumes)::

    {
        "dct:title": {
            "prefix":      "dct",
            "local_name":  "title",
            "uri":         "http://purl.org/dc/terms/title",
            "requirement": "mandatory",   # mandatory | recommended | optional | deprecated
            "label":       "Title",
            "description": "A name given to the Dataset.",
        },
        ...
    }

Data sources
------------
* ``shacl/dcat-ap-SHACL.ttl``     — base DCAT-AP terms (all NodeShape properties
  that carry ``shacl:name`` + ``shacl:path``)
* ``context/healthdcat-cardinality-rules.json`` — HealthDCAT-AP extension terms
  (healthdcatap: namespace); property names are extracted from the
  ``usage_note`` HTML fragment in each entry.

Prefix normalisation
--------------------
Rather than aliasing by prefix name (fragile), we use a URI-based lookup:
``_NS_URI_TO_CANONICAL_PREFIX`` maps well-known namespace URIs to the
canonical prefix name the UI templates expect.  For example, release-6 of
the HealthDCAT-AP SHACL TTL declares DC Terms under the prefix ``dc1:``
while earlier releases use ``dc:``.  Both are normalised to ``dct:`` via
their shared namespace URI ``http://purl.org/dc/terms/``.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# URI-based prefix normalisation.
# Different releases of the SHACL TTL may declare well-known namespaces under
# different prefixes (e.g. release-6 uses 'dc1:' and earlier releases use 'dc:'
# for http://purl.org/dc/terms/).  We key the canonical prefix to the namespace
# URI so that any prefix spelling in the source TTL is handled correctly.
# ---------------------------------------------------------------------------
_NS_URI_TO_CANONICAL_PREFIX: dict[str, str] = {
    'http://purl.org/dc/terms/': 'dct',  # always exposed as dct: in the UI
}

# Base URI for the healthdcatap: namespace (sourced from official example TTLs
# in the submodule: @prefix healthdcatap: <http://healthdataportal.eu/ns/health#>)
_HEALTHDCAT_PREFIX = 'healthdcatap'
_HEALTHDCAT_BASE_URI = 'http://healthdataportal.eu/ns/health#'

# Module-level cache: populated on first call to get_registry()
_registry_cache: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_registry(release_dir: Path) -> dict[str, Any]:
    """
    Return the in-memory schema dict for *release_dir*, loading and caching it
    on the first call.

    Parameters
    ----------
    release_dir:
        Absolute path to a release directory inside the ``health_dcat_ap/``
        submodule, e.g. ``BASE_DIR / "health_dcat_ap/public/releases/release-6"``.

    Returns
    -------
    dict keyed by prefixed semantics string.  Empty dict if the release
    directory or TTL file is missing.
    """
    global _registry_cache
    if _registry_cache is None:
        _registry_cache = _load(release_dir)
    return _registry_cache


def invalidate_cache() -> None:
    """Clear the module-level cache (useful in tests)."""
    global _registry_cache
    _registry_cache = None


# ---------------------------------------------------------------------------
# Internal — parsing
# ---------------------------------------------------------------------------


def _load(release_dir: Path) -> dict[str, Any]:
    shacl_ttl = release_dir / 'shacl' / 'dcat-ap-SHACL.ttl'
    cardinality_json = release_dir / 'context' / 'healthdcat-cardinality-rules.json'

    if not release_dir.is_dir():
        logger.warning(
            'HealthDCAT-AP release directory not found: %s — schema registry unavailable.',
            release_dir,
        )
        return {}

    if not shacl_ttl.exists():
        logger.warning(
            'SHACL TTL not found: %s — schema registry unavailable.',
            shacl_ttl,
        )
        return {}

    try:
        from rdflib import Graph  # type: ignore[import-untyped]
        from rdflib.namespace import SH  # type: ignore[import-untyped]
        from rdflib import Literal as RDFLiteral, URIRef  # noqa: F401
    except ImportError:
        logger.error(
            'rdflib is not installed. Install it with: pip install rdflib>=7.0.0'
        )
        return {}

    try:
        g = Graph()
        g.parse(str(shacl_ttl), format='turtle')
    except Exception:
        logger.exception('Failed to parse SHACL TTL: %s', shacl_ttl)
        return {}

    # Build prefix map: normalise to canonical prefix names by namespace URI.
    # This handles TTL files that declare the same namespace under different
    # prefix spellings across releases (e.g. 'dc:' vs 'dc1:' for dc/terms/).
    prefix_map: dict[str, str] = {}
    for pfx, ns in g.namespaces():
        pfx_str = str(pfx)
        ns_str = str(ns)
        if pfx_str:
            canonical = _NS_URI_TO_CANONICAL_PREFIX.get(ns_str, pfx_str)
            prefix_map[canonical] = ns_str

    # Always ensure healthdcatap base is registered (not in base SHACL)
    prefix_map.setdefault(_HEALTHDCAT_PREFIX, _HEALTHDCAT_BASE_URI)

    # Collect term data grouped by path URI
    # path_uri → {label, description, mandatory}
    by_path: dict[str, dict[str, Any]] = {}

    for subj in g.subjects(SH.path, None):
        path_node = g.value(subj, SH.path)
        if path_node is None:
            continue
        path_uri = str(path_node)

        # English shacl:name (label)
        label: str | None = None
        for val in g.objects(subj, SH.name):
            if isinstance(val, RDFLiteral):
                if not val.language or val.language == 'en':
                    label = str(val)
                    break
        if label is None:
            continue

        # English shacl:description
        description = ''
        for val in g.objects(subj, SH.description):
            if isinstance(val, RDFLiteral):
                if not val.language or val.language == 'en':
                    description = str(val)
                    break

        # Requirement from shacl:minCount
        min_count_node = g.value(subj, SH.minCount)
        has_mandatory = (
            min_count_node is not None and int(str(min_count_node)) >= 1
        )

        existing = by_path.get(path_uri)
        if existing is None:
            by_path[path_uri] = {
                'label': label,
                'description': description,
                'mandatory': has_mandatory,
            }
        elif has_mandatory and not existing['mandatory']:
            existing['mandatory'] = True

    # Build output dict
    result: dict[str, Any] = {}
    for path_uri, info in by_path.items():
        prefixed = _uri_to_prefixed(path_uri, prefix_map)
        if prefixed is None:
            continue
        colon_idx = prefixed.index(':')
        prefix = prefixed[:colon_idx]
        local_name = prefixed[colon_idx + 1:]
        requirement = 'mandatory' if info['mandatory'] else 'optional'
        result[prefixed] = {
            'prefix': prefix,
            'local_name': local_name,
            'uri': path_uri,
            'requirement': requirement,
            'label': info['label'],
            'description': info['description'],
        }

    # Merge HealthDCAT-AP-specific extension terms from the cardinality JSON
    if cardinality_json.exists():
        _merge_healthdcat_terms(cardinality_json, result)

    logger.info(
        'Schema registry loaded: %d terms from %s',
        len(result),
        release_dir,
    )
    return result


def _uri_to_prefixed(uri: str, prefix_map: dict[str, str]) -> str | None:
    """Convert a full URI to ``prefix:local`` form, or None if no prefix matches."""
    for prefix, base in prefix_map.items():
        if uri.startswith(base) and len(uri) > len(base):
            return f'{prefix}:{uri[len(base):]}'
    return None


def _merge_healthdcat_terms(
    json_path: Path,
    result: dict[str, Any],
) -> None:
    """
    Parse HealthDCAT-AP extension terms from ``healthdcat-cardinality-rules.json``
    and merge them into *result*.

    The JSON contains a ``PUBLIC`` object with human-readable property names as
    keys.  The actual RDF property name (e.g. ``healthdcatap:healthCategory``) is
    embedded in the ``usage_note`` HTML as::

        <a href="#healthdcatapXxx">healthdcatap:xxx</a>

    Only entries whose usage_note contains a ``healthdcatap:`` reference are
    added; entries already present from the SHACL TTL are not overwritten.
    """
    try:
        data = json.loads(json_path.read_text(encoding='utf-8'))
    except Exception:
        logger.exception('Failed to read HealthDCAT-AP cardinality JSON: %s', json_path)
        return

    cardinality_data: dict[str, Any] = data.get('PUBLIC', {})
    _req_map = {'mandatory': 'mandatory', 'recommended': 'recommended', 'optional': 'optional'}

    for term_label, term_info in cardinality_data.items():
        usage_note: str = term_info.get('usage_note', '')
        # Extract healthdcatap:propertyName from the usage_note HTML
        match = re.search(r'healthdcatap:(\w+)', usage_note)
        if not match:
            continue

        local_name = match.group(1)
        semantics = f'{_HEALTHDCAT_PREFIX}:{local_name}'

        if semantics in result:
            # Already present from SHACL — do not overwrite
            continue

        req_raw = str(term_info.get('requirement', 'optional')).lower()
        requirement = _req_map.get(req_raw, 'optional')

        result[semantics] = {
            'prefix': _HEALTHDCAT_PREFIX,
            'local_name': local_name,
            'uri': f'{_HEALTHDCAT_BASE_URI}{local_name}',
            'requirement': requirement,
            'label': term_label.title(),
            'description': term_info.get('definition', ''),
        }
