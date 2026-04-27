"""JSON-LD graph builder for metadata exports."""

from __future__ import annotations

import re

from shared.export_terms import ExportRdfClass, ResolvedExportProfile
from shared.export_types import (
    ExportWarning,
    JsonLdDocument,
    JsonLdGraph,
    JsonLdIdRef,
    JsonLdNode,
)
from shared.export_values import id_ref, is_http_uri, label_from_iri, values_for_reference_nodes

_CURIE_RE = re.compile(r'^([A-Za-z][A-Za-z0-9_-]*):[^/]')


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
        return id_ref(value)

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
        if not is_http_uri(iri):
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
        for value in values_for_reference_nodes(values):
            self.add_reference_node(
                value,
                classes,
                label=label_from_iri(value) if labels else None,
            )

    def document(self) -> JsonLdDocument:
        used: set[str] = set()
        collect_used_prefixes({'@graph': self.graph}, used)
        context = {key: value for key, value in self.profile.prefixes.items() if key in used}
        return {'@context': context, '@graph': self.graph}


def collect_used_prefixes(obj: object, prefixes: set[str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if not key.startswith('@'):
                match = _CURIE_RE.match(key)
                if match:
                    prefixes.add(match.group(1))
            collect_used_prefixes(value, prefixes)
        return

    if isinstance(obj, list):
        for item in obj:
            collect_used_prefixes(item, prefixes)
        return

    if isinstance(obj, str) and not obj.startswith('@'):
        match = _CURIE_RE.match(obj)
        if match:
            prefixes.add(match.group(1))
