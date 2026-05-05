"""Schema-registry-backed RDF terms used by export builders."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from schema_registry.types import SchemaRegistryContextProfile
from shared.export_context import get_export_context_profile
from shared.export_types import ExportWarning


class ExportEntity(StrEnum):
    """JSON-LD context classes that own exportable properties."""

    CATALOGUE = 'Catalogue'
    DATASET = 'Dataset'
    DISTRIBUTION = 'Distribution'


class ExportRdfClass(StrEnum):
    """Named HealthDCAT-AP/DCAT class terms required by generated reference nodes."""

    CONCEPT = 'Concept'
    LEGAL_RESOURCE = 'LegalResource'
    LICENCE_DOCUMENT = 'LicenceDocument'
    MEDIA_TYPE_OR_EXTENT = 'MediaTypeOrExtent'
    PROVENANCE_STATEMENT = 'ProvenanceStatement'
    RIGHTS_STATEMENT = 'RightsStatement'
    STANDARD = 'Standard'


class ExportValueKind(StrEnum):
    """Supported JSON-LD value shapes for declarative field export."""

    ID = 'id'
    ID_LIST = 'id_list'
    KEYWORD_LIST = 'keyword_list'
    LITERAL = 'literal'
    LITERAL_OR_ID = 'literal_or_id'
    LITERAL_OR_ID_LIST = 'literal_or_id_list'
    TYPED_ANY_URI = 'typed_any_uri'
    TYPED_DATETIME = 'typed_datetime'
    TYPED_NON_NEGATIVE_INTEGER = 'typed_non_negative_integer'


@dataclass(frozen=True, slots=True)
class ExportFieldSpec:
    """Declarative mapping from an export DTO attribute to a JSON-LD property."""

    attr: str
    entity: ExportEntity
    alias: str
    value_kind: ExportValueKind
    reference_classes: tuple[ExportRdfClass, ...] = ()
    reference_labels: bool = False


_ENTITY_CLASS_TERMS: dict[ExportEntity, str] = {
    ExportEntity.CATALOGUE: 'Catalogue',
    ExportEntity.DATASET: 'Dataset',
    ExportEntity.DISTRIBUTION: 'Distribution',
}


_EMPTY_CONTEXT_PROFILE: SchemaRegistryContextProfile = {
    'prefixes': {},
    'classes': {},
    'properties': {},
    'terms': {},
}


@dataclass(slots=True)
class ResolvedExportProfile:
    """Best-effort export profile that records missing RDF terms as warnings."""

    profile: SchemaRegistryContextProfile
    warnings: list[ExportWarning] = field(default_factory=list)
    _seen_warnings: set[tuple[str, str | None, str | None, str]] = field(default_factory=set)

    @classmethod
    def load(cls) -> ResolvedExportProfile:
        """Load the active profile, recording failures instead of raising."""
        resolved = cls(profile=_EMPTY_CONTEXT_PROFILE.copy())  # type: ignore[typeddict-item]
        try:
            resolved.profile = get_export_context_profile()
        except Exception as exc:
            resolved.warn(
                'profile_load_failed',
                f'HealthDCAT-AP export context profile could not be loaded: {exc}',
            )
            return resolved

        if not any(resolved.profile.values()):
            resolved.warn(
                'profile_empty',
                'HealthDCAT-AP export context profile is empty; metadata export is incomplete.',
            )
        return resolved

    @property
    def prefixes(self) -> dict[str, str]:
        return self.profile['prefixes']

    def warn(
        self,
        code: str,
        message: str,
        *,
        severity: str = 'warning',
        entity: str | None = None,
        alias: str | None = None,
    ) -> None:
        """Record a deduplicated warning."""
        key = (code, entity, alias, message)
        if key in self._seen_warnings:
            return
        self._seen_warnings.add(key)
        self.warnings.append(
            ExportWarning(
                code=code,
                message=message,
                severity=severity,
                entity=entity,
                alias=alias,
            )
        )

    def compact_iri(self, value: str) -> str:
        return compact_iri(value, self.profile)

    def rdf_class(self, term: ExportRdfClass) -> str | None:
        return self.named_class(term.value)

    def named_class(self, alias: str) -> str | None:
        value = self.profile['classes'].get(alias)
        if value is None:
            self.warn(
                'missing_class',
                f'Missing RDF class "{alias}" in HealthDCAT-AP context profile.',
                alias=alias,
            )
            return None
        return self.compact_iri(value)

    def entity_type(self, entity: ExportEntity) -> str | None:
        class_term = _ENTITY_CLASS_TERMS[entity]
        value = self.profile['classes'].get(class_term)
        if value is None:
            self.warn(
                'missing_class',
                f'Missing RDF class "{class_term}" for {entity.value} in HealthDCAT-AP context profile.',
                entity=entity.value,
                alias=class_term,
            )
            return None
        return self.compact_iri(value)

    def property(self, spec: ExportFieldSpec) -> str | None:
        return self.property_alias(spec.entity, spec.alias)

    def property_alias(self, entity: ExportEntity, alias: str) -> str | None:
        value = self.profile['properties'].get(entity.value, {}).get(alias)
        if value is None:
            self.warn(
                'missing_property',
                f'Missing RDF property "{alias}" for {entity.value} in HealthDCAT-AP context profile.',
                entity=entity.value,
                alias=alias,
            )
            return None
        return value

    def term(self, alias: str) -> str | None:
        value = self.profile['terms'].get(alias)
        if value is None:
            self.warn(
                'missing_term',
                f'Missing RDF term "{alias}" in HealthDCAT-AP context profile.',
                alias=alias,
            )
            return None
        return value

    def prefixed_name(self, prefix: str, local_name: str) -> str | None:
        if prefix not in self.profile['prefixes']:
            alias = f'{prefix}:{local_name}'
            self.warn(
                'missing_prefix',
                f'Missing RDF prefix "{prefix}" in HealthDCAT-AP context profile.',
                alias=alias,
            )
            return None
        return f'{prefix}:{local_name}'


def export_context_profile() -> SchemaRegistryContextProfile:
    """Return the active HealthDCAT-AP export context profile."""
    return get_export_context_profile()


def compact_iri(value: str, profile: SchemaRegistryContextProfile | None = None) -> str:
    """Return ``prefix:local`` when the active profile has a matching namespace."""
    if ':' in value and not value.startswith(('http://', 'https://')):
        return value

    active_profile = profile or export_context_profile()
    for prefix, namespace in active_profile['prefixes'].items():
        if value.startswith(namespace) and len(value) > len(namespace):
            return f'{prefix}:{value[len(namespace) :]}'
    return value
