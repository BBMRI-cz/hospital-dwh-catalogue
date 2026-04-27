"""HealthDCAT-AP Release 6 JSON-LD / Turtle export utilities."""

from __future__ import annotations

import re
from typing import Any

from shared.dtos import (
    ExportAgent,
    ExportCatalog,
    ExportContactPoint,
    ExportDataset,
    ExportDistribution,
)
from shared.export_context import clear_export_context_cache
from shared.export_serialization import dump_jsonld, serialise_jsonld_to_turtle
from shared.export_terms import (
    ExportEntity,
    ExportFieldSpec,
    ExportRdfClass,
    ExportValueKind,
    ResolvedExportProfile,
)
from shared.export_types import (
    ExportResource,
    ExportWarning,
    JsonLdContext,
    JsonLdDocument,
    JsonLdExportResult,
    JsonLdGraph,
    JsonLdIdRef,
    JsonLdLiteralOrUri,
    JsonLdNode,
    JsonLdTypedValue,
    TurtleExportResult,
)

_CURIE_RE = re.compile(r'^([A-Za-z][A-Za-z0-9_-]*):[^/]')
_IRI_LABEL_RE = re.compile(r'[/#]([^/#]+)[/#]?$')

_CATALOG_FIELDS: tuple[ExportFieldSpec, ...] = (
    ExportFieldSpec('title', ExportEntity.CATALOGUE, 'title', ExportValueKind.LITERAL),
    ExportFieldSpec(
        'description',
        ExportEntity.CATALOGUE,
        'description',
        ExportValueKind.LITERAL,
    ),
    ExportFieldSpec(
        'applicable_legislation',
        ExportEntity.CATALOGUE,
        'applicableLegislation',
        ExportValueKind.ID_LIST,
        reference_classes=(ExportRdfClass.LEGAL_RESOURCE,),
    ),
)

_DATASET_FIELDS: tuple[ExportFieldSpec, ...] = (
    ExportFieldSpec('title', ExportEntity.DATASET, 'title', ExportValueKind.LITERAL),
    ExportFieldSpec(
        'description',
        ExportEntity.DATASET,
        'description',
        ExportValueKind.LITERAL,
    ),
    ExportFieldSpec(
        'identifier',
        ExportEntity.DATASET,
        'identifier',
        ExportValueKind.TYPED_ANY_URI,
    ),
    ExportFieldSpec('version', ExportEntity.DATASET, 'version', ExportValueKind.LITERAL),
    ExportFieldSpec(
        'theme',
        ExportEntity.DATASET,
        'theme',
        ExportValueKind.ID_LIST,
        reference_classes=(ExportRdfClass.CONCEPT,),
        reference_labels=True,
    ),
    ExportFieldSpec(
        'conforms_to',
        ExportEntity.DATASET,
        'conformsTo',
        ExportValueKind.LITERAL_OR_ID_LIST,
        reference_classes=(ExportRdfClass.STANDARD,),
    ),
    ExportFieldSpec('issued', ExportEntity.DATASET, 'releaseDate', ExportValueKind.TYPED_DATETIME),
    ExportFieldSpec(
        'modified',
        ExportEntity.DATASET,
        'modificationDate',
        ExportValueKind.TYPED_DATETIME,
    ),
    ExportFieldSpec('keywords', ExportEntity.DATASET, 'keyword', ExportValueKind.KEYWORD_LIST),
    ExportFieldSpec(
        'access_rights',
        ExportEntity.DATASET,
        'accessRights',
        ExportValueKind.ID,
        reference_classes=(ExportRdfClass.RIGHTS_STATEMENT, ExportRdfClass.CONCEPT),
        reference_labels=True,
    ),
    ExportFieldSpec(
        'applicable_legislation',
        ExportEntity.DATASET,
        'applicableLegislation',
        ExportValueKind.ID_LIST,
        reference_classes=(ExportRdfClass.LEGAL_RESOURCE,),
    ),
    ExportFieldSpec(
        'health_category',
        ExportEntity.DATASET,
        'healthCategory',
        ExportValueKind.ID_LIST,
        reference_classes=(ExportRdfClass.CONCEPT,),
        reference_labels=True,
    ),
    ExportFieldSpec(
        'type',
        ExportEntity.DATASET,
        'type',
        ExportValueKind.ID_LIST,
        reference_classes=(ExportRdfClass.CONCEPT,),
        reference_labels=True,
    ),
)

_DISTRIBUTION_FIELDS: tuple[ExportFieldSpec, ...] = (
    ExportFieldSpec('title', ExportEntity.DISTRIBUTION, 'title', ExportValueKind.LITERAL),
    ExportFieldSpec(
        'description',
        ExportEntity.DISTRIBUTION,
        'description',
        ExportValueKind.LITERAL,
    ),
    ExportFieldSpec(
        'access_url',
        ExportEntity.DISTRIBUTION,
        'accessUrl',
        ExportValueKind.ID,
    ),
    ExportFieldSpec(
        'applicable_legislation',
        ExportEntity.DISTRIBUTION,
        'applicableLegislation',
        ExportValueKind.ID_LIST,
        reference_classes=(ExportRdfClass.LEGAL_RESOURCE,),
    ),
    ExportFieldSpec(
        'format',
        ExportEntity.DISTRIBUTION,
        'format',
        ExportValueKind.LITERAL_OR_ID,
        reference_classes=(ExportRdfClass.MEDIA_TYPE_OR_EXTENT,),
    ),
    ExportFieldSpec(
        'conforms_to',
        ExportEntity.DISTRIBUTION,
        'linkedSchemas',
        ExportValueKind.LITERAL_OR_ID_LIST,
        reference_classes=(ExportRdfClass.STANDARD,),
    ),
    ExportFieldSpec(
        'byte_size',
        ExportEntity.DISTRIBUTION,
        'byteSize',
        ExportValueKind.TYPED_NON_NEGATIVE_INTEGER,
    ),
    ExportFieldSpec(
        'rights',
        ExportEntity.DISTRIBUTION,
        'rights',
        ExportValueKind.LITERAL_OR_ID,
        reference_classes=(ExportRdfClass.RIGHTS_STATEMENT,),
    ),
    ExportFieldSpec(
        'licence',
        ExportEntity.DISTRIBUTION,
        'licence',
        ExportValueKind.LITERAL_OR_ID,
        reference_classes=(ExportRdfClass.LICENCE_DOCUMENT,),
    ),
    ExportFieldSpec(
        'release_date',
        ExportEntity.DISTRIBUTION,
        'releaseDate',
        ExportValueKind.TYPED_DATETIME,
    ),
    ExportFieldSpec(
        'modification_date',
        ExportEntity.DISTRIBUTION,
        'modificationDate',
        ExportValueKind.TYPED_DATETIME,
    ),
)

__all__ = [
    'build_complete_jsonld_result',
    'build_complete_turtle_result',
    'build_jsonld_result',
    'build_turtle_result',
    'clear_export_context_cache',
    'dump_jsonld',
    'has_distributions',
]


class JsonLdGraphBuilder:
    """Collect JSON-LD graph nodes and supporting reference nodes."""

    def __init__(self, profile: ResolvedExportProfile) -> None:
        self.profile = profile
        self.graph: JsonLdGraph = []
        self._seen: set[str] = set()

    @property
    def warnings(self) -> tuple[ExportWarning, ...]:
        return tuple(self.profile.warnings)

    def append(self, node: JsonLdNode) -> None:
        iri = node.get('@id')
        if not isinstance(iri, str):
            self.graph.append(node)
            return
        if iri in self._seen:
            return
        self.graph.append(node)
        self._seen.add(iri)

    def id_ref(self, value: str) -> JsonLdIdRef:
        return _id_ref(value)

    def set_property(
        self,
        node: JsonLdNode,
        property_name: str | None,
        value: object,
    ) -> None:
        if property_name is not None and value is not None:
            node[property_name] = value

    def set_type(self, node: JsonLdNode, rdf_types: list[str | None]) -> None:
        resolved_types = [rdf_type for rdf_type in rdf_types if rdf_type is not None]
        if not resolved_types:
            return
        node['@type'] = resolved_types[0] if len(resolved_types) == 1 else resolved_types

    def add_reference_node(
        self,
        iri: str,
        classes: tuple[ExportRdfClass, ...],
        *,
        label: str | None = None,
        description: str | None = None,
    ) -> None:
        if not _is_http_uri(iri):
            return

        node: JsonLdNode = {'@id': iri}
        self.set_type(node, [self.profile.rdf_class(term) for term in classes])
        if label:
            self.set_property(node, self.profile.term('skos:prefLabel'), label)
        if description:
            self.set_property(node, self.profile.term('dct:description'), description)
        self.append(node)

    def add_reference_nodes(
        self,
        values: object,
        classes: tuple[ExportRdfClass, ...],
        *,
        labels: bool = False,
    ) -> None:
        for value in _values_for_reference_nodes(values):
            self.add_reference_node(
                value,
                classes,
                label=_label_from_iri(value) if labels else None,
            )

    def document(self) -> JsonLdDocument:
        used: set[str] = set()
        _collect_used_prefixes({'@graph': self.graph}, used)
        full_context = _build_context(self.profile)
        context = {key: value for key, value in full_context.items() if key in used}
        return {'@context': context, '@graph': self.graph}


def _collect_used_prefixes(obj: object, prefixes: set[str]) -> None:
    """Recursively walk *obj* and collect CURIE prefixes used in keys and values."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if not key.startswith('@'):
                match = _CURIE_RE.match(key)
                if match:
                    prefixes.add(match.group(1))
            _collect_used_prefixes(value, prefixes)
        return

    if isinstance(obj, list):
        for item in obj:
            _collect_used_prefixes(item, prefixes)
        return

    if isinstance(obj, str) and not obj.startswith('@'):
        match = _CURIE_RE.match(obj)
        if match:
            prefixes.add(match.group(1))


def _build_context(profile: ResolvedExportProfile) -> JsonLdContext:
    """Return namespace prefixes resolved for this export build."""
    return profile.prefixes


def _catalog_iri(app: str, name: str) -> str | None:
    if _is_http_uri(name):
        return name
    return None


def _dataset_iri(identifier: str | None = None) -> str | None:
    """Return the dataset IRI from its identifier, or None when absent."""
    return identifier if identifier else None


def _distribution_iri(access_url: str | None = None) -> str | None:
    """Return the distribution IRI from its access URL, or None when absent."""
    return access_url if access_url else None


def _agent_iri(app: str, name: str) -> str | None:
    if _is_http_uri(name):
        return name
    return None


def _contact_point_iri(contact_point: ExportContactPoint) -> str | None:
    if contact_point.contact_page:
        return contact_point.contact_page
    if contact_point.email:
        return f'mailto:{contact_point.email}'
    return None


def _split_values(value: str | None) -> list[str]:
    return [item.strip() for item in (value or '').split(';') if item.strip()]


def _is_http_uri(value: str | None) -> bool:
    if not value:
        return False
    return value.startswith('http://') or value.startswith('https://')


def _id_ref(value: str) -> JsonLdIdRef:
    return {'@id': value}


def _maybe_uri_ref(value: str | None) -> JsonLdLiteralOrUri | None:
    if not value:
        return None
    if _is_http_uri(value):
        return _id_ref(value)
    return value


def _typed_value(value_type: str, value: str) -> JsonLdTypedValue:
    return {'@type': value_type, '@value': value}


def _typed_any_uri(
    value: str | None,
    profile: ResolvedExportProfile,
) -> JsonLdTypedValue | None:
    if not value:
        return None
    value_type = profile.prefixed_name('xsd', 'anyURI')
    return _typed_value(value_type, value) if value_type is not None else None


def _typed_datetime(
    value: str | None,
    profile: ResolvedExportProfile,
) -> JsonLdTypedValue | None:
    if not value:
        return None
    value_type = profile.prefixed_name('xsd', 'dateTime')
    return _typed_value(value_type, value) if value_type is not None else None


def _typed_non_negative_integer(
    value: int | None,
    profile: ResolvedExportProfile,
) -> JsonLdTypedValue | None:
    if value is None:
        return None
    value_type = profile.prefixed_name('xsd', 'nonNegativeInteger')
    return _typed_value(value_type, str(value)) if value_type is not None else None


def _label_from_iri(iri: str) -> str:
    match = _IRI_LABEL_RE.search(iri)
    if not match:
        return iri
    return match.group(1).replace('_', ' ').replace('-', ' ')


def _values_for_reference_nodes(values: object) -> list[str]:
    if isinstance(values, str):
        return [value for value in _split_values(values) if _is_http_uri(value)]
    if isinstance(values, list):
        result: list[str] = []
        for value in values:
            if isinstance(value, str) and _is_http_uri(value):
                result.append(value)
        return result
    return []


def _literal_or_id_list(values: str | None) -> list[JsonLdLiteralOrUri]:
    result: list[JsonLdLiteralOrUri] = []
    for value in _split_values(values):
        result.append(_id_ref(value) if _is_http_uri(value) else value)
    return result


def _id_list(values: str | None) -> list[JsonLdIdRef]:
    return [_id_ref(value) for value in _split_values(values) if _is_http_uri(value)]


def _jsonld_field_value(
    value: Any,
    kind: ExportValueKind,
    profile: ResolvedExportProfile,
):
    if kind == ExportValueKind.LITERAL:
        return value if value not in (None, '') else None
    if kind == ExportValueKind.KEYWORD_LIST:
        return value or None
    if kind == ExportValueKind.ID:
        return _id_ref(value) if value else None
    if kind == ExportValueKind.ID_LIST:
        values = _id_list(value)
        return values or None
    if kind == ExportValueKind.LITERAL_OR_ID:
        return _maybe_uri_ref(value)
    if kind == ExportValueKind.LITERAL_OR_ID_LIST:
        values = _literal_or_id_list(value)
        return values or None
    if kind == ExportValueKind.TYPED_ANY_URI:
        return _typed_any_uri(value, profile)
    if kind == ExportValueKind.TYPED_DATETIME:
        return _typed_datetime(value, profile)
    if kind == ExportValueKind.TYPED_NON_NEGATIVE_INTEGER:
        return _typed_non_negative_integer(value, profile)
    raise ValueError(f'Unsupported export value kind: {kind!r}')


def _apply_field_specs(
    node: JsonLdNode,
    source: object,
    field_specs: tuple[ExportFieldSpec, ...],
    builder: JsonLdGraphBuilder,
) -> None:
    for spec in field_specs:
        property_name = builder.profile.property(spec)
        if property_name is None:
            continue
        raw_value = getattr(source, spec.attr, None)
        value = _jsonld_field_value(raw_value, spec.value_kind, builder.profile)
        if value is None:
            continue

        node[property_name] = value
        if spec.reference_classes:
            builder.add_reference_nodes(
                raw_value,
                spec.reference_classes,
                labels=spec.reference_labels,
            )


def _provenance_node(value: str, builder: JsonLdGraphBuilder) -> JsonLdNode:
    node: JsonLdNode = {}
    builder.set_type(node, [builder.profile.rdf_class(ExportRdfClass.PROVENANCE_STATEMENT)])
    builder.set_property(node, builder.profile.term('dct:description'), value)
    return node


def _build_contact_point_node(
    contact_point: ExportContactPoint,
    builder: JsonLdGraphBuilder,
) -> JsonLdNode:
    node: JsonLdNode = {}
    builder.set_type(
        node,
        [builder.profile.named_class('ContactPoint'), builder.profile.named_class('Kind')],
    )
    contact_point_iri = _contact_point_iri(contact_point)
    if contact_point_iri is not None:
        node['@id'] = contact_point_iri
    if contact_point.email:
        builder.set_property(node, builder.profile.term('cv:email'), contact_point.email)
        builder.set_property(
            node,
            builder.profile.term('vcard:hasEmail'),
            _id_ref(f'mailto:{contact_point.email}'),
        )
    if contact_point.contact_page:
        builder.set_property(
            node,
            builder.profile.term('cv:contactPage'),
            _id_ref(contact_point.contact_page),
        )
        builder.set_property(
            node,
            builder.profile.term('vcard:hasURL'),
            _id_ref(contact_point.contact_page),
        )
    return node


def _ensure_contact_point(
    contact_point: ExportContactPoint | None,
    builder: JsonLdGraphBuilder,
) -> JsonLdIdRef | JsonLdNode | None:
    if contact_point is None:
        return None
    node = _build_contact_point_node(contact_point, builder)
    contact_point_iri = node.get('@id')
    if isinstance(contact_point_iri, str):
        builder.append(node)
        return _id_ref(contact_point_iri)
    return node


def _build_agent_node(agent: ExportAgent, builder: JsonLdGraphBuilder) -> JsonLdIdRef | JsonLdNode:
    contact_point_value = _ensure_contact_point(agent.contact_point, builder)
    node: JsonLdNode = {}
    builder.set_type(node, [builder.profile.named_class('Agent')])
    builder.set_property(node, builder.profile.term('foaf:name'), agent.name)
    agent_iri = _agent_iri(agent.app, agent.name)
    if agent_iri is not None:
        node['@id'] = agent_iri
    if agent.description:
        builder.set_property(node, builder.profile.term('dct:description'), agent.description)
    if contact_point_value is not None:
        builder.set_property(node, builder.profile.term('cv:contactPoint'), contact_point_value)
    if agent_iri is not None:
        builder.append(node)
        return _id_ref(agent_iri)
    return node


def _build_table_group(
    distribution: ExportDistribution,
    builder: JsonLdGraphBuilder,
) -> JsonLdNode | None:
    if not distribution.tables:
        return None
    table_property = builder.profile.term('csvw:table')
    column_property = builder.profile.term('csvw:column')
    if table_property is None or column_property is None:
        return None

    table_group: JsonLdNode = {table_property: []}
    builder.set_type(table_group, [builder.profile.named_class('TableGroup')])

    tables = table_group[table_property]
    assert isinstance(tables, list)
    for table in distribution.tables:
        table_node: JsonLdNode = {column_property: []}
        builder.set_type(table_node, [builder.profile.named_class('Table')])
        builder.set_property(table_node, builder.profile.term('csvw:name'), table.name)
        if table.title:
            builder.set_property(table_node, builder.profile.term('dct:title'), table.title)
        if table.description:
            builder.set_property(
                table_node,
                builder.profile.term('dct:description'),
                table.description,
            )
        if table.url:
            builder.set_property(table_node, builder.profile.term('csvw:url'), _id_ref(table.url))

        columns = table_node[column_property]
        assert isinstance(columns, list)
        for column in table.columns:
            column_node: JsonLdNode = {}
            builder.set_type(column_node, [builder.profile.named_class('Column')])
            builder.set_property(column_node, builder.profile.term('csvw:name'), column.name)
            if column.title:
                builder.set_property(column_node, builder.profile.term('dct:title'), column.title)
                builder.set_property(column_node, builder.profile.term('csvw:titles'), column.title)
            if column.description:
                builder.set_property(
                    column_node,
                    builder.profile.term('dct:description'),
                    column.description,
                )
            if column.datatype:
                builder.set_property(
                    column_node,
                    builder.profile.term('csvw:datatype'),
                    column.datatype,
                )
            if column.property_url:
                builder.set_property(
                    column_node,
                    builder.profile.term('csvw:propertyUrl'),
                    _id_ref(column.property_url),
                )
            columns.append(column_node)

        tables.append(table_node)

    return table_group


def _build_distribution_node(
    distribution: ExportDistribution,
    builder: JsonLdGraphBuilder,
) -> JsonLdNode:
    node: JsonLdNode = {}
    builder.set_type(node, [builder.profile.entity_type(ExportEntity.DISTRIBUTION)])
    iri = _distribution_iri(distribution.access_url)
    if iri is not None:
        node['@id'] = iri

    _apply_field_specs(node, distribution, _DISTRIBUTION_FIELDS, builder)

    sample = _build_table_group(distribution, builder)
    if sample is not None:
        builder.set_property(node, builder.profile.term('adms:sample'), sample)
    return node


def _build_dataset_node(
    dataset: ExportDataset,
    builder: JsonLdGraphBuilder,
    *,
    include_distributions: bool = True,
) -> JsonLdNode:
    publisher_value = _build_agent_node(dataset.publisher, builder) if dataset.publisher else None
    creator_value = _build_agent_node(dataset.creator, builder) if dataset.creator else None
    hdab_value = _build_agent_node(dataset.hdab, builder) if dataset.hdab else None
    custodian_value = _build_agent_node(dataset.custodian, builder) if dataset.custodian else None
    contact_point_value = _ensure_contact_point(dataset.contact_point, builder)

    node: JsonLdNode = {}
    builder.set_type(node, [builder.profile.entity_type(ExportEntity.DATASET)])
    iri = _dataset_iri(dataset.identifier)
    if iri is not None:
        node['@id'] = iri

    _apply_field_specs(node, dataset, _DATASET_FIELDS, builder)

    if publisher_value is not None:
        builder.set_property(
            node,
            builder.profile.property_alias(ExportEntity.DATASET, 'publisher'),
            publisher_value,
        )
    if creator_value is not None:
        builder.set_property(
            node,
            builder.profile.property_alias(ExportEntity.DATASET, 'creator'),
            creator_value,
        )
    # dct:source ranges to dcat:Dataset. A single-dataset export cannot
    # guarantee that the referenced dataset is present and profile-compatible.
    if contact_point_value is not None:
        builder.set_property(
            node,
            builder.profile.property_alias(ExportEntity.DATASET, 'contactPoint'),
            contact_point_value,
        )
    if dataset.provenance:
        builder.set_property(
            node,
            builder.profile.property_alias(ExportEntity.DATASET, 'provenance'),
            _provenance_node(dataset.provenance, builder),
        )
    if hdab_value is not None:
        builder.set_property(
            node,
            builder.profile.property_alias(ExportEntity.DATASET, 'hdab'),
            hdab_value,
        )
    if custodian_value is not None:
        builder.set_property(
            node,
            builder.profile.property_alias(ExportEntity.DATASET, 'custodian'),
            custodian_value,
        )
    if include_distributions and dataset.distributions:
        dist_refs = [
            _id_ref(iri)
            for distribution in dataset.distributions
            if (iri := _distribution_iri(distribution.access_url)) is not None
        ]
        if dist_refs:
            builder.set_property(
                node,
                builder.profile.property_alias(ExportEntity.DATASET, 'distribution'),
                dist_refs,
            )
    return node


def _add_distributions(dataset: ExportDataset, builder: JsonLdGraphBuilder) -> None:
    for distribution in dataset.distributions:
        builder.append(_build_distribution_node(distribution, builder))


def _build_catalog_node(
    catalog: ExportCatalog,
    builder: JsonLdGraphBuilder,
    *,
    dataset_refs: list[JsonLdIdRef],
) -> JsonLdNode:
    catalog_node: JsonLdNode = {}
    builder.set_type(catalog_node, [builder.profile.entity_type(ExportEntity.CATALOGUE)])
    builder.set_property(
        catalog_node,
        builder.profile.property_alias(ExportEntity.CATALOGUE, 'dataset'),
        dataset_refs,
    )
    catalog_iri = _catalog_iri(catalog.app, catalog.name)
    if catalog_iri is not None:
        catalog_node['@id'] = catalog_iri

    _apply_field_specs(catalog_node, catalog, _CATALOG_FIELDS, builder)

    if catalog.publisher is not None:
        builder.set_property(
            catalog_node,
            builder.profile.property_alias(ExportEntity.CATALOGUE, 'publisher'),
            _build_agent_node(catalog.publisher, builder),
        )
    return catalog_node


def _append_dataset_resource(
    dataset: ExportDataset,
    builder: JsonLdGraphBuilder,
    *,
    include_catalog: bool,
    include_distributions: bool = True,
) -> None:
    if include_catalog and dataset.catalog is not None:
        dataset_iri = _dataset_iri(dataset.identifier)
        dataset_refs = [_id_ref(dataset_iri)] if dataset_iri is not None else []
        builder.append(_build_catalog_node(dataset.catalog, builder, dataset_refs=dataset_refs))

    builder.append(
        _build_dataset_node(dataset, builder, include_distributions=include_distributions)
    )
    if include_distributions:
        _add_distributions(dataset, builder)


def _append_catalog_resource(
    catalog: ExportCatalog,
    builder: JsonLdGraphBuilder,
    *,
    include_distributions: bool = True,
) -> None:
    dataset_refs = [
        _id_ref(iri)
        for dataset in catalog.datasets
        if (iri := _dataset_iri(dataset.identifier)) is not None
    ]
    builder.append(_build_catalog_node(catalog, builder, dataset_refs=dataset_refs))

    for dataset in catalog.datasets:
        _append_dataset_resource(
            dataset,
            builder,
            include_catalog=False,
            include_distributions=include_distributions,
        )

def _build_resource_result(resource: ExportResource) -> JsonLdExportResult:
    builder = JsonLdGraphBuilder(ResolvedExportProfile.load())
    if isinstance(resource, ExportDataset):
        _append_dataset_resource(resource, builder, include_catalog=False)
    elif isinstance(resource, ExportCatalog):
        _append_catalog_resource(resource, builder)
    else:
        raise TypeError(f'Unsupported export resource: {type(resource)!r}')
    return JsonLdExportResult(document=builder.document(), warnings=builder.warnings)


def _build_complete_result(
    catalogs: list[ExportCatalog],
    orphan_datasets: list[ExportDataset],
    *,
    include_distributions: bool = True,
) -> JsonLdExportResult:
    builder = JsonLdGraphBuilder(ResolvedExportProfile.load())

    for catalog in catalogs:
        _append_catalog_resource(catalog, builder, include_distributions=include_distributions)

    for dataset in orphan_datasets:
        _append_dataset_resource(
            dataset,
            builder,
            include_catalog=False,
            include_distributions=include_distributions,
        )

    return JsonLdExportResult(document=builder.document(), warnings=builder.warnings)


def build_jsonld_result(resource: ExportResource) -> JsonLdExportResult:
    """Build a JSON-LD export document with non-fatal compatibility warnings."""
    return _build_resource_result(resource)


def build_complete_jsonld_result(
    catalogs: list[ExportCatalog],
    orphan_datasets: list[ExportDataset],
    *,
    include_distributions: bool = True,
) -> JsonLdExportResult:
    """Build an aggregate JSON-LD export with non-fatal compatibility warnings."""
    return _build_complete_result(
        catalogs,
        orphan_datasets,
        include_distributions=include_distributions,
    )


def has_distributions(dataset: ExportDataset) -> bool:
    """Return True if the export dataset contains at least one distribution."""
    return bool(dataset.distributions)


def build_turtle_result(resource: ExportResource) -> TurtleExportResult:
    """Serialise a JSON-LD export result to Turtle with compatibility warnings."""
    result = build_jsonld_result(resource)
    return TurtleExportResult(
        content=serialise_jsonld_to_turtle(result.document),
        warnings=result.warnings,
    )


def build_complete_turtle_result(
    catalogs: list[ExportCatalog],
    orphan_datasets: list[ExportDataset],
    *,
    include_distributions: bool = True,
) -> TurtleExportResult:
    """Serialise an aggregate JSON-LD export result to Turtle with warnings."""
    result = build_complete_jsonld_result(
        catalogs,
        orphan_datasets,
        include_distributions=include_distributions,
    )
    return TurtleExportResult(
        content=serialise_jsonld_to_turtle(result.document),
        warnings=result.warnings,
    )
