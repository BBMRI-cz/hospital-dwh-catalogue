"""Schema discovery and declarative RDF parsing specs for FAIR Genomes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from rdflib import Literal as RdfLiteral
from rdflib import URIRef
from rdflib.namespace import RDF, RDFS

ExtractorKind = Literal['literal', 'uri', 'multi_uri', 'multi_literal']
ValueType = Literal['string', 'datetime', 'int']

_NORMALISE_RE = re.compile(r'[^a-z0-9]+')


def _uri_local_name(uri: str) -> str:
    stripped = uri.rstrip('/#')
    if '#' in stripped:
        return stripped.rsplit('#', 1)[-1]
    return stripped.rsplit('/', 1)[-1]


def _snake_to_camel(value: str) -> str:
    head, *tail = value.split('_')
    return head + ''.join(part.capitalize() for part in tail)


def _normalise_identifier(value: str) -> str:
    return _NORMALISE_RE.sub('', value.lower())


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    extractor: ExtractorKind
    aliases: tuple[str, ...] = ()
    fk_target: str | None = None
    separator: str = ';'
    value_type: ValueType = 'string'

    def match_aliases(self) -> frozenset[str]:
        aliases = {self.name, _snake_to_camel(self.name), *self.aliases}
        return frozenset(_normalise_identifier(alias) for alias in aliases)


@dataclass(frozen=True, slots=True)
class EntitySpec:
    name: str
    fields: tuple[FieldSpec, ...]


@dataclass(slots=True)
class RawRecord:
    entity_name: str
    subject_uri: str
    values: dict[str, object]


@dataclass(slots=True)
class GraphSchema:
    entity_types: dict[str, tuple[URIRef, ...]]
    column_predicates: dict[str, dict[str, URIRef]]
    predicate_aliases: dict[str, dict[URIRef, frozenset[str]]]

    def predicate_candidates(self, entity_name: str, field: FieldSpec) -> tuple[URIRef, ...]:
        discovered = self.predicate_aliases.get(entity_name, {})
        matches = [
            predicate
            for predicate, aliases in discovered.items()
            if aliases & field.match_aliases()
        ]
        return tuple(matches)

    def subjects_for_entity(self, graph, entity_name: str) -> tuple[URIRef, ...]:
        subjects: set[URIRef] = set()

        for predicate in self.predicate_aliases.get(entity_name, {}):
            subjects.update(
                subject
                for subject in graph.subjects(predicate, None)
                if isinstance(subject, URIRef)
            )

        if not subjects:
            for type_uri in self.entity_types.get(entity_name, ()):
                subjects.update(
                    subject
                    for subject in graph.subjects(RDF.type, type_uri)
                    if isinstance(subject, URIRef)
                )

        return tuple(sorted(subjects, key=str))


ENTITY_SPECS: tuple[EntitySpec, ...] = (
    EntitySpec(
        name='ContactPoint',
        fields=(
            FieldSpec(name='email', extractor='literal'),
            FieldSpec(name='contact_page', extractor='uri'),
        ),
    ),
    EntitySpec(
        name='Agent',
        fields=(
            FieldSpec(name='name', extractor='literal'),
            FieldSpec(name='description', extractor='literal'),
            FieldSpec(name='contact_point', extractor='uri', fk_target='ContactPoint'),
        ),
    ),
    EntitySpec(
        name='Catalog',
        fields=(
            FieldSpec(name='name', extractor='literal'),
            FieldSpec(name='title', extractor='literal'),
            FieldSpec(name='description', extractor='literal'),
            FieldSpec(name='publisher', extractor='uri', fk_target='Agent'),
            FieldSpec(name='applicable_legislation', extractor='multi_uri'),
        ),
    ),
    EntitySpec(
        name='Dataset',
        fields=(
            FieldSpec(name='name', extractor='literal'),
            FieldSpec(name='title', extractor='literal'),
            FieldSpec(name='version', extractor='literal'),
            FieldSpec(name='description', extractor='literal'),
            FieldSpec(name='identifier', extractor='literal'),
            FieldSpec(name='type', extractor='multi_uri'),
            FieldSpec(name='theme', extractor='multi_uri'),
            FieldSpec(name='keyword', extractor='multi_literal', separator=','),
            FieldSpec(name='provenance', extractor='literal'),
            FieldSpec(name='conforms_to', extractor='multi_uri'),
            FieldSpec(name='access_rights', extractor='uri'),
            FieldSpec(name='applicable_legislation', extractor='multi_uri'),
            FieldSpec(name='health_category', extractor='multi_uri'),
            FieldSpec(name='issued', extractor='literal', value_type='datetime'),
            FieldSpec(name='modified', extractor='literal', value_type='datetime'),
            FieldSpec(name='hdab', extractor='uri', fk_target='Agent'),
            FieldSpec(name='contact_point', extractor='uri', fk_target='ContactPoint'),
            FieldSpec(name='publisher', extractor='uri', fk_target='Agent'),
            FieldSpec(name='creator', extractor='uri', fk_target='Agent'),
            FieldSpec(name='custodian', extractor='uri', fk_target='Agent'),
            FieldSpec(name='catalog', extractor='uri', fk_target='Catalog'),
            FieldSpec(name='source', extractor='uri', fk_target='Dataset'),
        ),
    ),
    EntitySpec(
        name='Distribution',
        fields=(
            FieldSpec(name='name', extractor='literal'),
            FieldSpec(name='dataset_name', extractor='uri', fk_target='Dataset'),
            FieldSpec(name='title', extractor='literal'),
            FieldSpec(name='description', extractor='literal'),
            FieldSpec(name='format', extractor='uri'),
            FieldSpec(name='conforms_to', extractor='multi_uri'),
            FieldSpec(name='byte_size', extractor='literal', value_type='int'),
            FieldSpec(name='rights', extractor='literal'),
            FieldSpec(name='release_date', extractor='literal', value_type='datetime'),
            FieldSpec(name='modification_date', extractor='literal', value_type='datetime'),
            FieldSpec(name='access_url', extractor='uri'),
            FieldSpec(name='applicable_legislation', extractor='multi_uri'),
            FieldSpec(name='licence', extractor='uri', aliases=('license',)),
        ),
    ),
)


def discover_graph_schema(
    graph, entity_specs: tuple[EntitySpec, ...] = ENTITY_SPECS
) -> GraphSchema:
    entity_names = {spec.name for spec in entity_specs}
    entity_types: dict[str, set[URIRef]] = {name: set() for name in entity_names}
    column_predicates: dict[str, dict[str, URIRef]] = {name: {} for name in entity_names}
    predicate_aliases: dict[str, dict[URIRef, frozenset[str]]] = {name: {} for name in entity_names}

    for subject, label in graph.subject_objects(RDFS.label):
        if not isinstance(subject, URIRef) or not isinstance(label, RdfLiteral):
            continue
        entity_name = str(label)
        if entity_name in entity_names:
            entity_types[entity_name].add(subject)

    for subject, domain in graph.subject_objects(RDFS.domain):
        if not isinstance(subject, URIRef) or not isinstance(domain, URIRef):
            continue
        label = graph.value(subject, RDFS.label)
        domain_label = graph.value(domain, RDFS.label)
        if not isinstance(label, RdfLiteral) or not isinstance(domain_label, RdfLiteral):
            continue

        entity_name = str(domain_label)
        if entity_name not in entity_names:
            continue

        entity_types[entity_name].add(domain)
        label_value = str(label)
        column_predicates[entity_name][label_value] = subject

        aliases = {_normalise_identifier(label_value)}
        defined_by = graph.value(subject, RDFS.isDefinedBy)
        if isinstance(defined_by, URIRef):
            aliases.add(_normalise_identifier(_uri_local_name(str(defined_by))))
        predicate_aliases[entity_name][subject] = frozenset(aliases)

    return GraphSchema(
        entity_types={
            entity_name: tuple(sorted(type_uris, key=str))
            for entity_name, type_uris in entity_types.items()
        },
        column_predicates=column_predicates,
        predicate_aliases=predicate_aliases,
    )
