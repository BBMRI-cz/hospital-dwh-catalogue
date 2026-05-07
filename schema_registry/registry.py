"""Load and cache HealthDCAT-AP term metadata from the checked-out release files."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, TypedDict

from schema_registry.types import (
    SchemaRegistryContextProfile,
    SchemaRegistryContextProperties,
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
_context_profile_cache: dict[Path, SchemaRegistryContextProfile] = {}


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


def get_context_profile(release_dir: Path) -> SchemaRegistryContextProfile:
    """Return the JSON-LD export context profile for a HealthDCAT-AP release."""
    resolved = release_dir.resolve()
    if resolved not in _context_profile_cache:
        _context_profile_cache[resolved] = _load_context_profile(resolved)
    return _context_profile_cache[resolved]


def invalidate_cache() -> None:
    """Clear the module-level cache."""
    _registry_cache.clear()
    _context_terms_cache.clear()
    _context_profile_cache.clear()


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
            'HealthDCAT-AP release directory not found: %s - schema registry unavailable.',
            release_dir,
        )
        return {}, {}

    if not shacl_ttl.exists():
        logger.warning(
            'SHACL TTL not found: %s - schema registry unavailable.',
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
    raw_context = _load_jsonld_context(release_dir)
    terms: SchemaRegistryContextTerms = {}
    for key, value in raw_context.items():
        iri = _context_term_iri(value)
        if iri is not None:
            terms[key] = iri
    return terms


def _load_context_profile(release_dir: Path) -> SchemaRegistryContextProfile:
    payload, prefix_map = _get_cached_entry(release_dir)
    raw_context = _load_jsonld_context(release_dir)
    classes, properties = _extract_context_profile_terms(raw_context, prefix_map)
    terms = _build_global_term_map(payload)
    _merge_context_property_terms(terms, properties)
    _merge_shacl_profile_terms(release_dir, prefix_map, classes, properties, terms)

    return {
        'prefixes': prefix_map,
        'classes': classes,
        'properties': properties,
        'terms': terms,
    }


def _merge_context_property_terms(
    terms: SchemaRegistryContextTerms,
    properties: SchemaRegistryContextProperties,
) -> None:
    for class_properties in properties.values():
        for alias, semantics in class_properties.items():
            _store_profile_term(terms, alias, semantics)


def _merge_shacl_profile_terms(
    release_dir: Path,
    prefix_map: SchemaRegistryPrefixMap,
    classes: SchemaRegistryContextTerms,
    properties: SchemaRegistryContextProperties,
    terms: SchemaRegistryContextTerms,
) -> None:
    try:
        from rdflib import Graph, URIRef  # type: ignore[import-untyped]
        from rdflib.namespace import SH  # type: ignore[import-untyped]
    except ImportError:
        logger.error('rdflib is not installed. Install it with: pip install rdflib>=7.0.0')
        return

    for ttl_path in _context_profile_shape_paths(release_dir):
        if not ttl_path.exists():
            continue

        graph = _parse_turtle_graph(Graph, ttl_path)
        if graph is None:
            continue

        for path_node in graph.objects(None, SH.path):
            if isinstance(path_node, URIRef):
                semantics = _uri_to_prefixed(str(path_node), prefix_map)
                if semantics is not None:
                    _store_profile_term(terms, semantics, semantics)

        _merge_shacl_class_properties(graph, SH, prefix_map, classes, properties)

        for class_predicate in (SH.targetClass, SH['class']):
            for class_node in graph.objects(None, class_predicate):
                if isinstance(class_node, URIRef):
                    _store_profile_class(classes, str(class_node), prefix_map)


def _merge_shacl_class_properties(
    graph,
    sh_namespace,
    prefix_map: SchemaRegistryPrefixMap,
    classes: SchemaRegistryContextTerms,
    properties: SchemaRegistryContextProperties,
) -> None:
    for shape_node, class_node in graph.subject_objects(sh_namespace.targetClass):
        class_uri = str(class_node)
        class_alias = _class_alias_for_uri(class_uri, classes, prefix_map)
        if class_alias is None:
            continue

        for property_shape in graph.objects(shape_node, sh_namespace.property):
            path_node = graph.value(property_shape, sh_namespace.path)
            if path_node is None:
                continue
            semantics = _uri_to_prefixed(str(path_node), prefix_map)
            if semantics is None:
                continue
            _store_class_property(properties, class_alias, semantics)


def _class_alias_for_uri(
    uri: str,
    classes: SchemaRegistryContextTerms,
    prefix_map: SchemaRegistryPrefixMap,
) -> str | None:
    for alias, class_uri in classes.items():
        if class_uri == uri and ':' not in alias:
            return alias

    semantics = _uri_to_prefixed(uri, prefix_map)
    if semantics is None:
        return None

    local_name = semantics.split(':', 1)[1]
    if local_name in classes:
        return local_name
    return local_name


def _context_profile_shape_paths(release_dir: Path) -> tuple[Path, ...]:
    html_shacl = release_dir / 'html' / 'shacl'
    return (
        release_dir / 'shacl' / 'dcat-ap-SHACL.ttl',
        html_shacl / 'public-shapes.ttl',
        html_shacl / 'restricted-shapes.ttl',
        html_shacl / 'non-public-shapes.ttl',
        html_shacl / 'range.ttl',
    )


def _load_jsonld_context(release_dir: Path) -> dict[str, Any]:
    context_json = release_dir / 'context' / 'dcat-ap.jsonld'
    if not context_json.exists():
        logger.warning(
            'JSON-LD context not found: %s - context term lookup unavailable.',
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
    return raw_context


def _extract_context_profile_terms(
    raw_context: dict[str, Any],
    prefix_map: SchemaRegistryPrefixMap,
) -> tuple[SchemaRegistryContextTerms, SchemaRegistryContextProperties]:
    classes: SchemaRegistryContextTerms = {}
    properties: SchemaRegistryContextProperties = {}

    for key, value in raw_context.items():
        iri = _context_term_iri(value)
        if iri is not None:
            classes[key] = iri
        if not isinstance(value, dict):
            continue

        nested_context = value.get('@context')
        if not isinstance(nested_context, dict):
            continue

        class_properties: dict[str, str] = {}
        for property_name, property_value in nested_context.items():
            property_iri = _context_term_iri(property_value)
            if property_iri is None:
                continue
            class_properties[property_name] = (
                _uri_to_prefixed(property_iri, prefix_map) or property_iri
            )
        if class_properties:
            properties[key] = class_properties

    return classes, properties


def _context_term_iri(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        iri = value.get('@id')
        if isinstance(iri, str):
            return iri
    return None


def _build_global_term_map(payload: SchemaRegistryPayload) -> SchemaRegistryContextTerms:
    terms: SchemaRegistryContextTerms = {}
    for semantics, term in payload.items():
        _store_profile_term(terms, term['local_name'], semantics)
    return terms


def _store_profile_term(
    terms: SchemaRegistryContextTerms,
    alias: str,
    semantics: str,
) -> None:
    terms.setdefault(alias, semantics)
    terms.setdefault(semantics, semantics)
    if ':' in semantics and not semantics.startswith(('http://', 'https://')):
        terms.setdefault(semantics.split(':', 1)[1], semantics)


def _store_profile_class(
    classes: SchemaRegistryContextTerms,
    uri: str,
    prefix_map: SchemaRegistryPrefixMap,
) -> None:
    semantics = _uri_to_prefixed(uri, prefix_map)
    if semantics is None:
        return

    local_name = semantics.split(':', 1)[1]
    classes.setdefault(local_name, uri)
    classes.setdefault(semantics, uri)


def _store_class_property(
    properties: SchemaRegistryContextProperties,
    class_alias: str,
    semantics: str,
) -> None:
    class_properties = properties.setdefault(class_alias, {})
    class_properties.setdefault(semantics, semantics)
    if ':' in semantics and not semantics.startswith(('http://', 'https://')):
        class_properties.setdefault(semantics.split(':', 1)[1], semantics)


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
