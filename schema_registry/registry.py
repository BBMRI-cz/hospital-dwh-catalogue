"""
HealthDCAT-AP Schema Registry — in-memory loader
==================================================

Parses the SHACL TTL and HealthDCAT-AP cardinality rules from the
``health_dcat_ap/`` git submodule and returns a plain dict keyed by
prefixed semantics string (e.g. ``"dct:title"``).

The dict is loaded once per Python process and cached in ``_registry_cache``
keyed by the resolved release directory path.  Call ``invalidate_cache()`` in
tests to force a reload.

Returned dict shape (matches what the JS schema modal consumes)::

    {
        "dct:title": {
            "prefix":      "dct",
            "local_name":  "title",
            "uri":         "http://purl.org/dc/terms/title",
            "requirement": "mandatory",   # mandatory | recommended | optional | deprecated
            "cardinality": "1..*",        # from cardinality JSON (empty if unknown)
            "label":       "Title",
            "description": "A name given to the Dataset.",
        },
        ...
    }

Data sources
------------
* ``shacl/dcat-ap-SHACL.ttl``     — base DCAT-AP terms (all NodeShape properties
  that carry ``shacl:name`` + ``shacl:path``)
* ``context/healthdcat-cardinality-rules.json`` — HealthDCAT-AP cardinality rules;
  property names are extracted from the ``usage_note`` HTML ``<a>`` tag in each
  entry.  For terms already in the SHACL result, the JSON updates ``requirement``
  (three-tier: mandatory / recommended / optional) and ``cardinality``.  New
  ``healthdcatap:`` terms not present in the SHACL TTL are added from the JSON.

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
from typing import TypedDict

from schema_registry.types import (
    SchemaRegistryPayload,
    SchemaRegistryPrefixMap,
    SchemaRequirement,
)

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

# Module-level cache: keyed by resolved release_dir path so that different
# release versions (or override_settings in tests) get independent caches.
_registry_cache: dict[Path, tuple[SchemaRegistryPayload, SchemaRegistryPrefixMap]] = {}


class _PathTermInfo(TypedDict):
    label: str
    description: str
    mandatory: bool


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_registry(release_dir: Path) -> SchemaRegistryPayload:
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
    resolved = release_dir.resolve()
    if resolved not in _registry_cache:
        _registry_cache[resolved] = _load(release_dir)
    return _registry_cache[resolved][0]


def get_namespace_prefixes(release_dir: Path) -> SchemaRegistryPrefixMap:
    """
    Return the namespace prefix map parsed from the SHACL TTL for *release_dir*.

    Keys are canonical prefix names (e.g. ``"dct"``), values are namespace
    base URIs (e.g. ``"http://purl.org/dc/terms/"``).

    The map is derived from the ``@prefix`` declarations in the SHACL TTL,
    with URI-based normalisation applied (see ``_NS_URI_TO_CANONICAL_PREFIX``).
    Returns an empty dict if the submodule or rdflib is unavailable.
    """
    global _registry_cache
    resolved = release_dir.resolve()
    if resolved not in _registry_cache:
        _registry_cache[resolved] = _load(release_dir)
    return _registry_cache[resolved][1]


def invalidate_cache() -> None:
    """Clear the module-level cache (useful in tests)."""
    global _registry_cache
    _registry_cache = {}


# ---------------------------------------------------------------------------
# Internal — parsing
# ---------------------------------------------------------------------------


def _load(release_dir: Path) -> tuple[SchemaRegistryPayload, SchemaRegistryPrefixMap]:
    shacl_ttl = release_dir / 'shacl' / 'dcat-ap-SHACL.ttl'
    cardinality_json = release_dir / 'context' / 'healthdcat-cardinality-rules.json'

    if not release_dir.is_dir():
        logger.warning(
            'HealthDCAT-AP release directory not found: %s — schema registry unavailable.',
            release_dir,
        )
        return {}, {}

    if not shacl_ttl.exists():
        logger.warning(
            'SHACL TTL not found: %s — schema registry unavailable.',
            shacl_ttl,
        )
        return {}, {}

    try:
        from rdflib import Graph  # type: ignore[import-untyped]
        from rdflib import Literal as RDFLiteral
        from rdflib.namespace import SH  # type: ignore[import-untyped]
    except ImportError:
        logger.error('rdflib is not installed. Install it with: pip install rdflib>=7.0.0')
        return {}, {}

    try:
        g = Graph()
        g.parse(str(shacl_ttl), format='turtle')
    except Exception:
        logger.exception('Failed to parse SHACL TTL: %s', shacl_ttl)
        return {}, {}

    # Build prefix map: normalise to canonical prefix names by namespace URI.
    # This handles TTL files that declare the same namespace under different
    # prefix spellings across releases (e.g. 'dc:' vs 'dc1:' for dc/terms/).
    prefix_map: SchemaRegistryPrefixMap = {}
    for pfx, ns in g.namespaces():
        pfx_str = str(pfx)
        ns_str = str(ns)
        if pfx_str:
            canonical = _NS_URI_TO_CANONICAL_PREFIX.get(ns_str, pfx_str)
            prefix_map[canonical] = ns_str

    # Also harvest prefixes from the HealthDCAT-AP public shapes TTL.
    # This file declares HealthDCAT-AP specific namespaces that are absent
    # from the base DCAT-AP SHACL TTL: healthdcatap, geodcatap, dcatap,
    # dpv, org, csvw, and others.
    health_shapes_ttl = release_dir / 'html' / 'shacl' / 'public-shapes.ttl'
    if health_shapes_ttl.exists():
        try:
            g2 = Graph()
            g2.parse(str(health_shapes_ttl), format='turtle')
            for pfx, ns in g2.namespaces():
                pfx_str = str(pfx)
                ns_str = str(ns)
                if pfx_str and pfx_str not in prefix_map:
                    canonical = _NS_URI_TO_CANONICAL_PREFIX.get(ns_str, pfx_str)
                    prefix_map[canonical] = ns_str
        except Exception:
            logger.warning(
                'Could not parse HealthDCAT-AP shapes TTL for namespace prefixes: %s',
                health_shapes_ttl,
            )

    # Collect term data grouped by path URI
    # path_uri → {label, description, mandatory}
    by_path: dict[str, _PathTermInfo] = {}

    for subj in g.subjects(SH.path, None):
        path_node = g.value(subj, SH.path)
        if path_node is None:
            continue
        path_uri = str(path_node)

        # English shacl:name (label)
        label: str | None = None
        for val in g.objects(subj, SH.name):
            if isinstance(val, RDFLiteral) and (not val.language or val.language == 'en'):
                label = str(val)
                break
        if label is None:
            continue

        # English shacl:description
        description = ''
        for val in g.objects(subj, SH.description):
            if isinstance(val, RDFLiteral) and (not val.language or val.language == 'en'):
                description = str(val)
                break

        # Requirement from shacl:minCount
        min_count_node = g.value(subj, SH.minCount)
        has_mandatory = min_count_node is not None and int(str(min_count_node)) >= 1

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
    result: SchemaRegistryPayload = {}
    for path_uri, info in by_path.items():
        prefixed = _uri_to_prefixed(path_uri, prefix_map)
        if prefixed is None:
            continue
        colon_idx = prefixed.index(':')
        prefix = prefixed[:colon_idx]
        local_name = prefixed[colon_idx + 1 :]
        requirement: SchemaRequirement = 'mandatory' if info['mandatory'] else 'optional'
        result[prefixed] = {
            'prefix': prefix,
            'local_name': local_name,
            'uri': path_uri,
            'requirement': requirement,
            'cardinality': '',
            'label': info['label'],
            'description': info['description'],
        }

    # Merge HealthDCAT-AP-specific extension terms from the cardinality JSON
    if cardinality_json.exists():
        _merge_healthdcat_terms(cardinality_json, result, prefix_map)

    logger.info(
        'Schema registry loaded: %d terms from %s',
        len(result),
        release_dir,
    )
    return result, prefix_map


def _uri_to_prefixed(uri: str, prefix_map: dict[str, str]) -> str | None:
    """Convert a full URI to ``prefix:local`` form, or None if no prefix matches."""
    for prefix, base in prefix_map.items():
        if uri.startswith(base) and len(uri) > len(base):
            return f'{prefix}:{uri[len(base) :]}'
    return None


def _merge_healthdcat_terms(
    json_path: Path,
    result: SchemaRegistryPayload,
    prefix_map: SchemaRegistryPrefixMap,
) -> None:
    """
    Parse HealthDCAT-AP cardinality rules from ``healthdcat-cardinality-rules.json``
    and merge them into *result*.

    The JSON contains a ``PUBLIC`` object with human-readable property names as
    keys.  The actual RDF property name (e.g. ``dct:title``,
    ``healthdcatap:healthCategory``) is embedded in the ``usage_note`` HTML
    inside an ``<a>`` link::

        <a href="#healthdcatapXxx">healthdcatap:xxx</a>

    For terms **already present** from the SHACL TTL, ``requirement`` is updated
    from the JSON (SHACL only distinguishes mandatory vs optional; the JSON
    provides the authoritative three-tier scheme: mandatory / recommended /
    optional) and ``cardinality`` is set from the JSON ``card`` field.

    For terms not already present from the SHACL TTL, a full entry is created
    when the term prefix is known in the parsed namespace map.
    """
    try:
        data = json.loads(json_path.read_text(encoding='utf-8'))
    except Exception:
        logger.exception('Failed to read HealthDCAT-AP cardinality JSON: %s', json_path)
        return

    cardinality_data: dict[str, object] = data.get('PUBLIC', {})
    _req_map: dict[str, SchemaRequirement] = {
        'mandatory': 'mandatory',
        'recommended': 'recommended',
        'optional': 'optional',
        'deprecated': 'deprecated',
    }

    for term_label, term_info in cardinality_data.items():
        if not isinstance(term_info, dict):
            continue
        usage_note: str = term_info.get('usage_note', '')
        # Extract prefix:propertyName from the <a> tag in the usage_note HTML.
        # Anchoring to '>' avoids false positives from mentions of prefixed
        # terms in the descriptive text (e.g. "healthdcatap:hdab" mentioned
        # inside the "qualified attribution" entry's prose).
        match = re.search(r'>(\w+):(\w+)', usage_note)
        if not match:
            logger.debug(
                'Cardinality JSON entry "%s" has no prefix:local reference '
                'in usage_note <a> tag — skipped.',
                term_label,
            )
            continue

        prefix = match.group(1)
        local_name = match.group(2)
        semantics = f'{prefix}:{local_name}'

        req_raw = str(term_info.get('requirement', 'optional')).lower()
        requirement = _req_map.get(req_raw, 'optional')
        cardinality = str(term_info.get('card', ''))

        if semantics in result:
            # Update requirement and cardinality from the authoritative JSON.
            result[semantics]['requirement'] = requirement
            result[semantics]['cardinality'] = cardinality
            continue

        namespace_uri = prefix_map.get(prefix)
        if not namespace_uri:
            logger.warning(
                'Prefix "%s" missing from namespace map while processing %s; '
                'skipping synthesized term %s.',
                prefix,
                json_path,
                semantics,
            )
            continue

        result[semantics] = {
            'prefix': prefix,
            'local_name': local_name,
            'uri': f'{namespace_uri}{local_name}',
            'requirement': requirement,
            'cardinality': cardinality,
            'label': term_label.title(),
            'description': term_info.get('definition', ''),
        }
