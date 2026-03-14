"""
Schema Registry Service Layer
==============================

This module is the ONLY public API for callers that need schema registry data.
All access to SchemaVersion, SchemaTerm, and SchemaFieldBinding must go through
these functions — never import the models directly in views, serialisers, or
export scripts.

Stability contract
------------------
This API is intentionally stable so that:
  * The hardcoded v6 seed source (v6_definitions.py) can later be replaced by a
    SHACL/TTL importer without changing any caller.
  * Tests written against this API need not change when the underlying data
    source changes.

Translation strategy
--------------------
Labels and descriptions are stored in English in the DB as `base_label_en` /
`base_description_en`.  At runtime, `_translate()` looks up a gettext msgid:

    schema.term.<term_key>.label
    schema.term.<term_key>.description

If the translation catalogue returns a string that differs from the msgid
(i.e. a real translation exists), that string is returned.  Otherwise the
stored English base text is used as the fallback.

Future: SHACL / TTL importer hook
-----------------------------------
# TODO(future): add the following function when the SHACL/TTL importer is built:
#
#   def import_from_shacl(ttl_source: str | Path, version_slug: str) -> SchemaVersion:
#       '''
#       Parse a SHACL/TTL file and upsert its terms and bindings into the DB.
#
#       Parameters
#       ----------
#       ttl_source:   path to a local .ttl file OR a URL string.
#       version_slug: slug for the SchemaVersion row to create/update.
#
#       Returns the SchemaVersion that was created or updated.
#
#       This function must produce SchemaVersion, SchemaPrefix, SchemaTerm, and
#       SchemaFieldBinding rows in exactly the same format as seed_schema_v6.
#       The service functions below must continue to work without modification
#       after this importer runs.
#       '''
#       raise NotImplementedError('SHACL/TTL importer is not yet implemented.')
"""

from __future__ import annotations

import logging
from typing import Any

from django.utils import translation

from schema_registry.models import SchemaFieldBinding, SchemaTerm, SchemaVersion

logger = logging.getLogger(__name__)


# ── Internal helpers ─────────────────────────────────────────────────────────


def _get_active_version() -> SchemaVersion:
    """Return the active SchemaVersion. Raises DoesNotExist if none is active."""
    return SchemaVersion.objects.get(is_active=True)


def _translate(msgid: str, fallback: str, lang: str | None) -> str:
    """
    Return the localised string for *msgid*, or *fallback* if no translation
    is registered.

    When *lang* is provided the Django translation context is temporarily
    activated for that language; otherwise the current active language is used.

    A translation is considered absent when gettext returns the msgid unchanged
    (which is Django's default when no entry exists in the PO catalogue).
    """
    if lang is not None:
        with translation.override(lang):
            translated = translation.gettext(msgid)
    else:
        translated = translation.gettext(msgid)

    # If Django found no entry it returns the msgid as-is — fall back to English.
    return fallback if translated == msgid else translated


# ── Public API ────────────────────────────────────────────────────────────────


def get_registry_version() -> SchemaVersion:
    """
    Return the currently active SchemaVersion.

    Raises
    ------
    SchemaVersion.DoesNotExist
        If no SchemaVersion with is_active=True exists.
    """
    return _get_active_version()


def list_terms(level: str | None = None) -> list[SchemaTerm]:
    """
    Return all SchemaTerm rows for the active schema version.

    Parameters
    ----------
    level:
        When provided, only terms whose ``levels`` JSON array contains this
        string are returned (e.g. ``level="Dataset"``).
    """
    version = _get_active_version()
    qs = SchemaTerm.objects.filter(schema_version=version).order_by('display_order', 'term_key')
    terms = list(qs)
    if level is not None:
        # Filter in Python: JSONField __contains is not available on SQLite.
        # The term count is small (O(tens)) so in-memory filtering is fine.
        terms = [t for t in terms if level in (t.levels or [])]
    return terms


def get_term(term_key: str) -> SchemaTerm:
    """
    Return the SchemaTerm with the given *term_key* for the active version.

    Raises
    ------
    SchemaTerm.DoesNotExist
        If the term_key does not exist for the active version.
    """
    version = _get_active_version()
    return SchemaTerm.objects.get(schema_version=version, term_key=term_key)


def list_bindings(table: str | None = None) -> list[SchemaFieldBinding]:
    """
    Return all SchemaFieldBinding rows for the active schema version.

    Parameters
    ----------
    table:
        When provided, only bindings for the named table are returned.
    """
    version = _get_active_version()
    qs = (
        SchemaFieldBinding.objects
        .filter(schema_version=version)
        .select_related('schema_term')
        .order_by('table_name', 'display_order')
    )
    if table is not None:
        qs = qs.filter(table_name=table)
    return list(qs)


def get_binding(table: str, column: str | None = None) -> SchemaFieldBinding:
    """
    Return the SchemaFieldBinding for the given *table* and *column*.

    Pass ``column=None`` to retrieve the entity (table-level) binding.

    Raises
    ------
    SchemaFieldBinding.DoesNotExist
        If no matching binding exists for the active version.
    """
    version = _get_active_version()
    return SchemaFieldBinding.objects.select_related('schema_term').get(
        schema_version=version,
        table_name=table,
        column_name=column,
    )


def describe_term(term_key: str, lang: str | None = None) -> dict[str, Any]:
    """
    Return a JSON-serialisable dict describing a single term.

    The ``label`` and ``description`` values are localised via gettext with
    fallback to the stored English base text.

    Returns
    -------
    dict with keys:
        term_key, semantics, prefixed_name, uri, requirement, label,
        description, levels
    """
    term = get_term(term_key)

    label_msgid = f'schema.term.{term_key}.label'
    desc_msgid = f'schema.term.{term_key}.description'

    return {
        'term_key': term.term_key,
        'semantics': term.semantics,
        'prefixed_name': term.semantics,   # same value; kept for API symmetry
        'uri': term.uri,
        'requirement': term.requirement,
        'label': _translate(label_msgid, term.base_label_en, lang),
        'description': _translate(desc_msgid, term.base_description_en, lang),
        'levels': term.levels,
    }


def describe_binding(
    table: str,
    column: str | None = None,
    lang: str | None = None,
) -> dict[str, Any]:
    """
    Return a JSON-serialisable dict describing a single field binding.

    The ``label`` and ``description`` use the binding-level English strings
    (which may differ from the term label in context) localised via the same
    gettext pattern as ``describe_term``.

    Returns
    -------
    dict with keys:
        table, column, type, ref_table, term_key, semantics, uri,
        label, description, is_entity
    """
    binding = get_binding(table, column)
    term = binding.schema_term

    # Binding label/description use the same msgid pattern as the term.
    # If a PO file has a binding-specific override under the term's msgid,
    # that wins; otherwise the binding's own English text is the fallback.
    label_msgid = f'schema.term.{term.term_key}.label'
    desc_msgid = f'schema.term.{term.term_key}.description'

    return {
        'table': binding.table_name,
        'column': binding.column_name,
        'type': binding.column_type,
        'ref_table': binding.ref_table,
        'term_key': term.term_key,
        'semantics': term.semantics,
        'uri': term.uri,
        'label': _translate(label_msgid, binding.label_en, lang),
        'description': _translate(desc_msgid, binding.description_en, lang),
        'is_entity': binding.is_entity,
    }


def export_registry_snapshot() -> dict[str, Any]:
    """
    Return a fully JSON-serialisable snapshot of the active schema version.

    Includes the version metadata, all prefix mappings, all terms, and all
    bindings.  Values are plain Python types (no lazy translation objects).

    Note: this is a lightweight structural export.  Full JSON-LD / RDF export
    is not implemented here.

    # TODO(future): replace or extend this function with a proper JSON-LD / RDF
    #   serialiser once the SHACL/TTL importer is in place.  The function
    #   signature must remain stable.
    """
    version = _get_active_version()

    prefixes = {
        p.prefix: p.base_uri
        for p in version.prefixes.order_by('prefix')
    }

    terms = [
        {
            'term_key': t.term_key,
            'semantics': t.semantics,
            'uri': t.uri,
            'requirement': t.requirement,
            'levels': t.levels,
            'label_en': t.base_label_en,
            'description_en': t.base_description_en,
            'display_order': t.display_order,
        }
        for t in version.terms.order_by('display_order', 'term_key')
    ]

    bindings = [
        {
            'table_name': b.table_name,
            'column_name': b.column_name,
            'column_type': b.column_type,
            'ref_table': b.ref_table,
            'term_key': b.schema_term.term_key,
            'semantics': b.schema_term.semantics,
            'uri': b.schema_term.uri,
            'label_en': b.label_en,
            'description_en': b.description_en,
            'is_entity': b.is_entity,
            'display_order': b.display_order,
        }
        for b in version.bindings.select_related('schema_term').order_by('table_name', 'display_order')
    ]

    return {
        'schema_version': {
            'slug': version.slug,
            'label': version.label,
            'is_active': version.is_active,
        },
        'prefixes': prefixes,
        'terms': terms,
        'bindings': bindings,
    }
