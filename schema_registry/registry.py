"""Load and cache HealthDCAT-AP term metadata from the checked-out release files."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, TypedDict

from schema_registry.types import (
    SchemaRegistryContextTerms,
    SchemaRegistryPayload,
    SchemaRegistryPrefixMap,
    SchemaRequirement,
)

logger = logging.getLogger(__name__)

# Some releases rename well-known prefixes, but the UI expects stable keys.
_NS_URI_TO_CANONICAL_PREFIX: dict[str, str] = {
    'http://purl.org/dc/terms/': 'dct',
}
_USAGE_NOTE_SEMANTICS_RE = re.compile(r'>(\w+):(\w+)')
_REQUIREMENT_BY_NAME: dict[str, SchemaRequirement] = {
    'mandatory': 'mandatory',
    'recommended': 'recommended',
    'optional': 'optional',
    'deprecated': 'deprecated',
}
_registry_cache: dict[Path, tuple[SchemaRegistryPayload, SchemaRegistryPrefixMap]] = {}
_context_terms_cache: dict[Path, SchemaRegistryContextTerms] = {}


class _PathTermInfo(TypedDict):
    label: str
    description: str
    mandatory: bool


def get_registry(release_dir: Path) -> SchemaRegistryPayload:
    """Return the cached term payload for a HealthDCAT-AP release directory."""
    return _get_cached_entry(release_dir)[0]


def get_namespace_prefixes(release_dir: Path) -> SchemaRegistryPrefixMap:
    """Return the cached namespace prefix map for a HealthDCAT-AP release directory."""
    return _get_cached_entry(release_dir)[1]


def get_context_terms(release_dir: Path) -> SchemaRegistryContextTerms:
    """Return named JSON-LD context terms for a HealthDCAT-AP release directory."""
    resolved = release_dir.resolve()
    if resolved not in _context_terms_cache:
        _context_terms_cache[resolved] = _load_context_terms(resolved)
    return _context_terms_cache[resolved]


def invalidate_cache() -> None:
    """Clear the module-level cache."""
    _registry_cache.clear()
    _context_terms_cache.clear()


def _get_cached_entry(release_dir: Path) -> tuple[SchemaRegistryPayload, SchemaRegistryPrefixMap]:
    resolved = release_dir.resolve()
    if resolved not in _registry_cache:
        _registry_cache[resolved] = _load(resolved)
    return _registry_cache[resolved]


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

    shacl_graph = _parse_turtle_graph(Graph, shacl_ttl)
    if shacl_graph is None:
        return {}, {}

    prefix_map = _build_prefix_map(Graph, shacl_graph, release_dir)
    result = _extract_terms(shacl_graph, SH, RDFLiteral, prefix_map)

    if cardinality_json.exists():
        _merge_healthdcat_terms(cardinality_json, result, prefix_map)

    logger.info('Schema registry loaded: %d terms from %s', len(result), release_dir)
    return result, prefix_map


def _load_context_terms(release_dir: Path) -> SchemaRegistryContextTerms:
    context_json = release_dir / 'context' / 'dcat-ap.jsonld'
    if not context_json.exists():
        logger.warning(
            'JSON-LD context not found: %s — context term lookup unavailable.',
            context_json,
        )
        return {}

    try:
        data = json.loads(context_json.read_text(encoding='utf-8'))
    except Exception:
        logger.exception('Failed to parse JSON-LD context: %s', context_json)
        return {}

    raw_context = data.get('@context')
    if not isinstance(raw_context, dict):
        logger.warning('JSON-LD context has no top-level @context object: %s', context_json)
        return {}

    terms: SchemaRegistryContextTerms = {}
    for key, value in raw_context.items():
        if isinstance(value, str):
            terms[key] = value
            continue
        if isinstance(value, dict):
            iri = value.get('@id')
            if isinstance(iri, str):
                terms[key] = iri
    return terms


def _parse_turtle_graph(graph_cls, path: Path):
    try:
        graph = graph_cls()
        graph.parse(str(path), format='turtle')
        return graph
    except Exception:
        logger.exception('Failed to parse SHACL TTL: %s', path)
        return None


def _build_prefix_map(graph_cls, shacl_graph, release_dir: Path) -> SchemaRegistryPrefixMap:
    prefix_map: SchemaRegistryPrefixMap = {}
    _merge_graph_prefixes(prefix_map, shacl_graph)

    # The public-shapes file carries HealthDCAT-AP-specific prefixes that do not
    # always appear in the base DCAT-AP SHACL export.
    health_shapes_ttl = release_dir / 'html' / 'shacl' / 'public-shapes.ttl'
    if health_shapes_ttl.exists():
        try:
            health_shapes_graph = graph_cls()
            health_shapes_graph.parse(str(health_shapes_ttl), format='turtle')
        except Exception:
            logger.warning(
                'Could not parse HealthDCAT-AP shapes TTL for namespace prefixes: %s',
                health_shapes_ttl,
            )
        else:
            _merge_graph_prefixes(prefix_map, health_shapes_graph, overwrite=False)

    return prefix_map


def _merge_graph_prefixes(
    prefix_map: SchemaRegistryPrefixMap,
    graph,
    *,
    overwrite: bool = True,
) -> None:
    for prefix_name, namespace in graph.namespaces():
        prefix = str(prefix_name)
        namespace_uri = str(namespace)
        if not prefix:
            continue
        canonical_prefix = _NS_URI_TO_CANONICAL_PREFIX.get(namespace_uri, prefix)
        if overwrite:
            prefix_map[canonical_prefix] = namespace_uri
        else:
            prefix_map.setdefault(canonical_prefix, namespace_uri)


def _extract_terms(graph, sh_namespace, literal_cls, prefix_map) -> SchemaRegistryPayload:
    by_path: dict[str, _PathTermInfo] = {}

    for subject in graph.subjects(sh_namespace.path, None):
        path_node = graph.value(subject, sh_namespace.path)
        if path_node is None:
            continue

        label = _first_english_literal(graph, subject, sh_namespace.name, literal_cls)
        if label is None:
            continue

        path_uri = str(path_node)
        _store_term_info(
            by_path,
            path_uri=path_uri,
            label=label,
            description=_first_english_literal(
                graph, subject, sh_namespace.description, literal_cls
            )
            or '',
            mandatory=_is_mandatory_term(graph, subject, sh_namespace),
        )

    result: SchemaRegistryPayload = {}
    for path_uri, info in by_path.items():
        semantics = _uri_to_prefixed(path_uri, prefix_map)
        if semantics is None:
            continue
        result[semantics] = _build_term_payload(
            semantics,
            uri=path_uri,
            requirement='mandatory' if info['mandatory'] else 'optional',
            cardinality='',
            label=info['label'],
            description=info['description'],
        )

    return result


def _store_term_info(
    by_path: dict[str, _PathTermInfo],
    *,
    path_uri: str,
    label: str,
    description: str,
    mandatory: bool,
) -> None:
    existing = by_path.get(path_uri)
    if existing is None:
        by_path[path_uri] = {
            'label': label,
            'description': description,
            'mandatory': mandatory,
        }
        return

    if mandatory and not existing['mandatory']:
        existing['mandatory'] = True


def _first_english_literal(graph, subject, predicate, literal_cls) -> str | None:
    for value in graph.objects(subject, predicate):
        if isinstance(value, literal_cls) and (not value.language or value.language == 'en'):
            return str(value)
    return None


def _is_mandatory_term(graph, subject, sh_namespace) -> bool:
    min_count_node = graph.value(subject, sh_namespace.minCount)
    return min_count_node is not None and int(str(min_count_node)) >= 1


def _build_term_payload(
    semantics: str,
    *,
    uri: str,
    requirement: SchemaRequirement,
    cardinality: str,
    label: str,
    description: str,
) -> dict[str, str]:
    prefix, local_name = semantics.split(':', 1)
    return {
        'prefix': prefix,
        'local_name': local_name,
        'uri': uri,
        'requirement': requirement,
        'cardinality': cardinality,
        'label': label,
        'description': description,
    }


def _uri_to_prefixed(uri: str, prefix_map: dict[str, str]) -> str | None:
    """Convert a full URI to ``prefix:local`` form."""
    for prefix, base in prefix_map.items():
        if uri.startswith(base) and len(uri) > len(base):
            return f'{prefix}:{uri[len(base) :]}'
    return None


def _merge_healthdcat_terms(
    json_path: Path,
    result: SchemaRegistryPayload,
    prefix_map: SchemaRegistryPrefixMap,
) -> None:
    try:
        data = json.loads(json_path.read_text(encoding='utf-8'))
    except Exception:
        logger.exception('Failed to read HealthDCAT-AP cardinality JSON: %s', json_path)
        return

    cardinality_data = data.get('PUBLIC', {})
    if not isinstance(cardinality_data, dict):
        return

    for term_label, term_info in cardinality_data.items():
        if not isinstance(term_info, dict):
            continue

        semantics = _extract_semantics(term_info.get('usage_note', ''), term_label)
        if semantics is None:
            continue

        requirement = _REQUIREMENT_BY_NAME.get(
            str(term_info.get('requirement', 'optional')).lower(),
            'optional',
        )
        cardinality = str(term_info.get('card', ''))

        # SHACL tells us whether a term is mandatory; the cardinality JSON is
        # the source for the full mandatory/recommended/optional classification.
        if semantics in result:
            result[semantics]['requirement'] = requirement
            result[semantics]['cardinality'] = cardinality
            continue

        prefix, local_name = semantics.split(':', 1)
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

        result[semantics] = _build_term_payload(
            semantics,
            uri=f'{namespace_uri}{local_name}',
            requirement=requirement,
            cardinality=cardinality,
            label=str(term_label).title(),
            description=str(term_info.get('definition', '')),
        )


def _extract_semantics(usage_note: Any, term_label: Any) -> str | None:
    match = _USAGE_NOTE_SEMANTICS_RE.search(str(usage_note))
    if match is not None:
        return f'{match.group(1)}:{match.group(2)}'

    logger.debug(
        'Cardinality JSON entry "%s" has no prefix:local reference in usage_note <a> tag.',
        term_label,
    )
    return None
