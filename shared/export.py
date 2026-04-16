"""HealthDCAT-AP Release 6 JSON-LD / Turtle export utilities."""

from __future__ import annotations

import re

from shared.dtos import (
    ExportAgent,
    ExportCatalog,
    ExportContactPoint,
    ExportDataset,
    ExportDistribution,
)
from shared.export_context import clear_export_context_cache, get_export_context_prefixes
from shared.export_serialization import dump_jsonld, serialise_jsonld_to_turtle
from shared.export_types import (
    ExportResource,
    JsonLdAgentNode,
    JsonLdAgentValue,
    JsonLdCatalogNode,
    JsonLdColumnNode,
    JsonLdContactPointNode,
    JsonLdContactPointValue,
    JsonLdContext,
    JsonLdDatasetNode,
    JsonLdDistributionNode,
    JsonLdDocument,
    JsonLdGraph,
    JsonLdGraphNode,
    JsonLdIdRef,
    JsonLdIdRefList,
    JsonLdLiteralOrUri,
    JsonLdLiteralOrUriList,
    JsonLdTableGroupNode,
    JsonLdTableNode,
    JsonLdTypedValue,
)

_CURIE_RE = re.compile(r'^([A-Za-z][A-Za-z0-9_-]*):[^/]')

__all__ = [
    'build_complete_jsonld',
    'build_complete_turtle',
    'build_jsonld',
    'build_turtle',
    'clear_export_context_cache',
    'dump_jsonld',
    'has_distributions',
]


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


def _build_context() -> JsonLdContext:
    """Load namespace prefixes from the schema registry cache."""
    return get_export_context_prefixes()


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


def _typed_any_uri(value: str | None) -> JsonLdTypedValue | None:
    if not value:
        return None
    return _typed_value('xsd:anyURI', value)


def _typed_datetime(value: str | None) -> JsonLdTypedValue | None:
    if not value:
        return None
    return _typed_value('xsd:dateTime', value)


def _append_node(graph: JsonLdGraph, seen: set[str], node: JsonLdGraphNode) -> None:
    iri = node.get('@id')
    if iri is None:
        graph.append(node)
        return
    if iri in seen:
        return
    graph.append(node)
    seen.add(iri)


def _build_contact_point_node(contact_point: ExportContactPoint) -> JsonLdContactPointNode:
    node: JsonLdContactPointNode = {'@type': ['cv:ContactPoint', 'vcard:Kind']}
    contact_point_iri = _contact_point_iri(contact_point)
    if contact_point_iri is not None:
        node['@id'] = contact_point_iri
    if contact_point.email:
        node['cv:email'] = contact_point.email
        node['vcard:hasEmail'] = _id_ref(f'mailto:{contact_point.email}')
    if contact_point.contact_page:
        node['cv:contactPage'] = _id_ref(contact_point.contact_page)
        node['vcard:hasURL'] = _id_ref(contact_point.contact_page)
    return node


def _ensure_contact_point(
    contact_point: ExportContactPoint | None,
    graph: JsonLdGraph,
    seen: set[str],
) -> JsonLdContactPointValue | None:
    if contact_point is None:
        return None
    node = _build_contact_point_node(contact_point)
    contact_point_iri = node.get('@id')
    if contact_point_iri is not None:
        _append_node(graph, seen, node)
        return _id_ref(contact_point_iri)
    return node


def _build_agent_node(agent: ExportAgent, graph: JsonLdGraph, seen: set[str]) -> JsonLdAgentValue:
    contact_point_value = _ensure_contact_point(agent.contact_point, graph, seen)
    node: JsonLdAgentNode = {
        '@type': 'foaf:Agent',
        'foaf:name': agent.name,
    }
    agent_iri = _agent_iri(agent.app, agent.name)
    if agent_iri is not None:
        node['@id'] = agent_iri
    if agent.description:
        node['dct:description'] = agent.description
    if contact_point_value is not None:
        node['cv:contactPoint'] = contact_point_value
    if agent_iri is not None:
        _append_node(graph, seen, node)
        return _id_ref(agent_iri)
    return node


def _uri_list(values: str | None) -> JsonLdIdRefList:
    return [_id_ref(value) for value in _split_values(values) if _is_http_uri(value)]


def _literal_or_uri_list(values: str | None) -> JsonLdLiteralOrUriList:
    result: JsonLdLiteralOrUriList = []
    for value in _split_values(values):
        result.append(_id_ref(value) if _is_http_uri(value) else value)
    return result


def _build_table_group(distribution: ExportDistribution) -> JsonLdTableGroupNode | None:
    if not distribution.tables:
        return None
    table_group: JsonLdTableGroupNode = {
        '@type': 'csvw:TableGroup',
        'csvw:table': [],
    }

    for table in distribution.tables:
        table_node: JsonLdTableNode = {
            '@type': 'csvw:Table',
            'csvw:name': table.name,
            'csvw:column': [],
        }
        if table.title:
            table_node['dct:title'] = table.title
        if table.description:
            table_node['dct:description'] = table.description
        if table.url:
            table_node['csvw:url'] = _id_ref(table.url)

        columns: list[JsonLdColumnNode] = []
        for column in table.columns:
            column_node: JsonLdColumnNode = {
                '@type': 'csvw:Column',
                'csvw:name': column.name,
            }
            if column.title:
                column_node['dct:title'] = column.title
            if column.description:
                column_node['dct:description'] = column.description
            if column.datatype:
                column_node['csvw:datatype'] = column.datatype
            if column.property_url:
                column_node['csvw:propertyUrl'] = _id_ref(column.property_url)
            columns.append(column_node)

        table_node['csvw:column'] = columns
        table_group['csvw:table'].append(table_node)

    return table_group


def _build_distribution_node(distribution: ExportDistribution) -> JsonLdDistributionNode:
    node: JsonLdDistributionNode = {
        '@type': 'dcat:Distribution',
    }
    iri = _distribution_iri(distribution.access_url)
    if iri is not None:
        node['@id'] = iri
    if distribution.title:
        node['dct:title'] = distribution.title
    if distribution.description:
        node['dct:description'] = distribution.description
    if distribution.access_url:
        node['dcat:accessURL'] = _id_ref(distribution.access_url)
    if distribution.applicable_legislation:
        legislation = _uri_list(distribution.applicable_legislation)
        if legislation:
            node['dcatap:applicableLegislation'] = legislation
    format_value = _maybe_uri_ref(distribution.format)
    if format_value is not None:
        node['dct:format'] = format_value
    conforms_to = _literal_or_uri_list(distribution.conforms_to)
    if conforms_to:
        node['dct:conformsTo'] = conforms_to
    if distribution.byte_size is not None:
        node['dcat:byteSize'] = distribution.byte_size
    rights_value = _maybe_uri_ref(distribution.rights)
    if rights_value is not None:
        node['dct:rights'] = rights_value
    licence_value = _maybe_uri_ref(distribution.licence)
    if licence_value is not None:
        node['dct:license'] = licence_value
    issued = _typed_datetime(distribution.release_date)
    if issued is not None:
        node['dct:issued'] = issued
    modified = _typed_datetime(distribution.modification_date)
    if modified is not None:
        node['dct:modified'] = modified
    sample = _build_table_group(distribution)
    if sample is not None:
        node['adms:sample'] = sample
    return node


def _build_dataset_node(
    dataset: ExportDataset,
    graph: JsonLdGraph,
    seen: set[str],
    *,
    include_distributions: bool = True,
) -> JsonLdDatasetNode:
    publisher_value = (
        _build_agent_node(dataset.publisher, graph, seen) if dataset.publisher else None
    )
    creator_value = _build_agent_node(dataset.creator, graph, seen) if dataset.creator else None
    hdab_value = _build_agent_node(dataset.hdab, graph, seen) if dataset.hdab else None
    custodian_value = (
        _build_agent_node(dataset.custodian, graph, seen) if dataset.custodian else None
    )
    contact_point_value = _ensure_contact_point(dataset.contact_point, graph, seen)

    node: JsonLdDatasetNode = {
        '@type': 'dcat:Dataset',
    }
    iri = _dataset_iri(dataset.identifier)
    if iri is not None:
        node['@id'] = iri
    if dataset.title:
        node['dct:title'] = dataset.title
    if dataset.description:
        node['dct:description'] = dataset.description
    identifier = _typed_any_uri(dataset.identifier)
    if identifier is not None:
        node['dct:identifier'] = identifier
    if dataset.version:
        node['dcat:version'] = dataset.version
    theme_values = _uri_list(dataset.theme)
    if theme_values:
        node['dcat:theme'] = theme_values
    if publisher_value is not None:
        node['dct:publisher'] = publisher_value
    if creator_value is not None:
        node['dct:creator'] = creator_value
    conforms_to = _literal_or_uri_list(dataset.conforms_to)
    if conforms_to:
        node['dct:conformsTo'] = conforms_to
    issued = _typed_datetime(dataset.issued)
    if issued is not None:
        node['dct:issued'] = issued
    modified = _typed_datetime(dataset.modified)
    if modified is not None:
        node['dct:modified'] = modified
    if dataset.keywords:
        node['dcat:keyword'] = dataset.keywords
    if dataset.source_name:
        source_iri = _dataset_iri(dataset.source_identifier)
        if source_iri is not None:
            node['dct:source'] = _id_ref(source_iri)
    if contact_point_value is not None:
        node['dcat:contactPoint'] = contact_point_value
    if dataset.provenance:
        node['dct:provenance'] = dataset.provenance
    if dataset.access_rights:
        node['dct:accessRights'] = _id_ref(dataset.access_rights)
    applicable_legislation = _uri_list(dataset.applicable_legislation)
    if applicable_legislation:
        node['dcatap:applicableLegislation'] = applicable_legislation
    health_category_values = _uri_list(dataset.health_category)
    if health_category_values:
        node['healthdcatap:healthCategory'] = health_category_values
    if hdab_value is not None:
        node['healthdcatap:hdab'] = hdab_value
    if custodian_value is not None:
        node['geodcatap:custodian'] = custodian_value
    dataset_types = _uri_list(dataset.type)
    if dataset_types:
        node['dct:type'] = dataset_types
    if include_distributions and dataset.distributions:
        dist_refs = [
            _id_ref(iri)
            for distribution in dataset.distributions
            if (iri := _distribution_iri(distribution.access_url)) is not None
        ]
        if dist_refs:
            node['dcat:distribution'] = dist_refs
    return node


def _add_distributions(dataset: ExportDataset, graph: JsonLdGraph, seen: set[str]) -> None:
    for distribution in dataset.distributions:
        _append_node(graph, seen, _build_distribution_node(distribution))


def _append_dataset_resource(
    dataset: ExportDataset,
    graph: JsonLdGraph,
    seen: set[str],
    *,
    include_catalog: bool,
    include_distributions: bool = True,
) -> None:
    if include_catalog and dataset.catalog is not None:
        dataset_iri = _dataset_iri(dataset.identifier)
        dataset_refs = [_id_ref(dataset_iri)] if dataset_iri is not None else []
        catalog_node: JsonLdCatalogNode = {
            '@type': 'dcat:Catalog',
            'dcat:dataset': dataset_refs,
        }
        catalog_iri = _catalog_iri(dataset.catalog.app, dataset.catalog.name)
        if catalog_iri is not None:
            catalog_node['@id'] = catalog_iri
        if dataset.catalog.title:
            catalog_node['dct:title'] = dataset.catalog.title
        if dataset.catalog.description:
            catalog_node['dct:description'] = dataset.catalog.description
        if dataset.catalog.applicable_legislation:
            legislation = _uri_list(dataset.catalog.applicable_legislation)
            if legislation:
                catalog_node['dcatap:applicableLegislation'] = legislation
        if dataset.catalog.publisher is not None:
            catalog_node['dct:publisher'] = _build_agent_node(
                dataset.catalog.publisher, graph, seen
            )
        _append_node(graph, seen, catalog_node)

    dataset_node = _build_dataset_node(
        dataset, graph, seen, include_distributions=include_distributions
    )
    _append_node(graph, seen, dataset_node)
    if include_distributions:
        _add_distributions(dataset, graph, seen)


def _dataset_graph(dataset: ExportDataset) -> JsonLdGraph:
    graph: JsonLdGraph = []
    seen: set[str] = set()

    _append_dataset_resource(dataset, graph, seen, include_catalog=True)
    return graph


def _append_catalog_resource(
    catalog: ExportCatalog,
    graph: JsonLdGraph,
    seen: set[str],
    *,
    include_distributions: bool = True,
) -> None:
    catalog_node: JsonLdCatalogNode = {
        '@type': 'dcat:Catalog',
        'dcat:dataset': [
            _id_ref(iri)
            for dataset in catalog.datasets
            if (iri := _dataset_iri(dataset.identifier)) is not None
        ],
    }
    catalog_iri = _catalog_iri(catalog.app, catalog.name)
    if catalog_iri is not None:
        catalog_node['@id'] = catalog_iri
    if catalog.title:
        catalog_node['dct:title'] = catalog.title
    if catalog.description:
        catalog_node['dct:description'] = catalog.description
    if catalog.applicable_legislation:
        legislation = _uri_list(catalog.applicable_legislation)
        if legislation:
            catalog_node['dcatap:applicableLegislation'] = legislation
    if catalog.publisher is not None:
        catalog_node['dct:publisher'] = _build_agent_node(catalog.publisher, graph, seen)
    _append_node(graph, seen, catalog_node)

    for dataset in catalog.datasets:
        _append_dataset_resource(
            dataset, graph, seen, include_catalog=False, include_distributions=include_distributions
        )


def _catalog_graph(catalog: ExportCatalog) -> JsonLdGraph:
    graph: JsonLdGraph = []
    seen: set[str] = set()

    _append_catalog_resource(catalog, graph, seen)

    return graph


def _complete_graph(
    catalogs: list[ExportCatalog],
    orphan_datasets: list[ExportDataset],
    *,
    include_distributions: bool = True,
) -> JsonLdGraph:
    graph: JsonLdGraph = []
    seen: set[str] = set()

    for catalog in catalogs:
        _append_catalog_resource(catalog, graph, seen, include_distributions=include_distributions)

    for dataset in orphan_datasets:
        _append_dataset_resource(
            dataset, graph, seen, include_catalog=False, include_distributions=include_distributions
        )

    return graph


def _build_document(graph: JsonLdGraph) -> JsonLdDocument:
    used: set[str] = set()
    _collect_used_prefixes({'@graph': graph}, used)

    full_context = _build_context()
    context = {key: value for key, value in full_context.items() if key in used}
    return {'@context': context, '@graph': graph}


def build_jsonld(resource: ExportResource) -> JsonLdDocument:
    """Build a HealthDCAT-AP Release 6 JSON-LD document for a dataset or catalog."""
    if isinstance(resource, ExportDataset):
        graph = _dataset_graph(resource)
    elif isinstance(resource, ExportCatalog):
        graph = _catalog_graph(resource)
    else:
        raise TypeError(f'Unsupported export resource: {type(resource)!r}')

    return _build_document(graph)


def build_complete_jsonld(
    catalogs: list[ExportCatalog],
    orphan_datasets: list[ExportDataset],
    *,
    include_distributions: bool = True,
) -> JsonLdDocument:
    """Build one aggregate JSON-LD export document for all catalog resources."""
    return _build_document(
        _complete_graph(catalogs, orphan_datasets, include_distributions=include_distributions)
    )


def has_distributions(dataset: ExportDataset) -> bool:
    """Return True if the export dataset contains at least one distribution."""
    return bool(dataset.distributions)


def build_turtle(resource: ExportResource) -> str:
    """Serialise the JSON-LD export document to Turtle."""
    return serialise_jsonld_to_turtle(build_jsonld(resource))


def build_complete_turtle(
    catalogs: list[ExportCatalog],
    orphan_datasets: list[ExportDataset],
    *,
    include_distributions: bool = True,
) -> str:
    """Serialise the aggregate JSON-LD export document to Turtle."""
    return serialise_jsonld_to_turtle(
        build_complete_jsonld(
            catalogs,
            orphan_datasets,
            include_distributions=include_distributions,
        )
    )
