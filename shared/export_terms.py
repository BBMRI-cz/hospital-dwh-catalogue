"""Schema-registry-backed RDF terms used by export builders."""

from __future__ import annotations

from enum import StrEnum

from shared.export_context import get_export_context_terms


class ExportRdfClass(StrEnum):
    """Named HealthDCAT/DCAT class terms required by generated reference nodes."""

    CONCEPT = 'Concept'
    LEGAL_RESOURCE = 'LegalResource'
    LICENCE_DOCUMENT = 'LicenceDocument'
    MEDIA_TYPE_OR_EXTENT = 'MediaTypeOrExtent'
    PROVENANCE_STATEMENT = 'ProvenanceStatement'
    RIGHTS_STATEMENT = 'RightsStatement'
    STANDARD = 'Standard'


def rdf_class(term: ExportRdfClass) -> str:
    """Return the IRI for a named RDF class from the active JSON-LD context."""
    return get_export_context_terms().get(term.value, term.value)
