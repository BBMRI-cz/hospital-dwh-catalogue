"""
Management command: seed_schema_v6

Populates the default database with Health DCAT-AP v6 schema definitions.

Behaviour
---------
* Idempotent — safe to run multiple times; uses update_or_create throughout.
* Creates SchemaVersion(slug="v6") and marks it active if no active version exists.
* Creates/updates SchemaPrefix rows from PREFIX_MAP.
* Creates/updates SchemaTerm rows, deriving prefix/local_name/URI from semantics.
* Creates/updates SchemaFieldBinding rows.

Validation (raises CommandError and does NOT write to the DB on failure):
  1. Every semantics string in TERMS must resolve to a non-empty URI via PREFIX_MAP.
  2. Every term_key in BINDINGS must reference an existing entry in TERMS.
  3. No duplicate (table_name, column_name) pairs in BINDINGS input.

Future: SHACL/TTL importer
---------------------------
# TODO(future): replace the import of v6_definitions below with a call to
#   schema_registry.shacl_importer.load(ttl_path) that returns
#   (PREFIX_MAP, TERMS, BINDINGS) in the same format.  This command's logic
#   will remain unchanged; only the data source changes.
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from schema_registry.models import SchemaFieldBinding, SchemaPrefix, SchemaTerm, SchemaVersion
from schema_registry.v6_definitions import BINDINGS, PREFIX_MAP, TERMS, VERSION_LABEL, VERSION_SLUG

logger = logging.getLogger(__name__)


def _resolve_uri(semantics: str, prefix_map: dict[str, str]) -> tuple[str, str, str]:
    """
    Split a prefixed name (e.g. "dct:identifier") into (prefix, local_name, full_uri).

    Raises ValueError if the prefix is not in prefix_map or the semantics
    string is not in 'prefix:local' format.
    """
    if ':' not in semantics:
        raise ValueError(f'Semantics "{semantics}" is not in prefix:local format.')
    prefix, local_name = semantics.split(':', 1)
    if prefix not in prefix_map:
        raise ValueError(f'Prefix "{prefix}" from semantics "{semantics}" is not in PREFIX_MAP.')
    base_uri = prefix_map[prefix]
    if not base_uri:
        raise ValueError(f'Prefix "{prefix}" has an empty base_uri in PREFIX_MAP.')
    return prefix, local_name, base_uri + local_name


class Command(BaseCommand):
    help = (
        'Seed the default database with Health DCAT-AP v6 schema definitions. '
        'Idempotent — safe to run multiple times.'
    )

    def handle(self, *args: Any, **options: Any) -> None:
        self._validate_definitions()

        with transaction.atomic():
            version = self._seed_version()
            self._seed_prefixes(version)
            term_map = self._seed_terms(version)
            self._seed_bindings(version, term_map)

        self.stdout.write(self.style.SUCCESS(f'Schema v6 seed complete (version pk={version.pk}).'))

    # ── Validation ───────────────────────────────────────────────────────────

    def _validate_definitions(self) -> None:
        """Pre-flight checks before touching the DB."""
        self.stdout.write('Validating v6 definitions…')

        # 1. All semantics must resolve.
        for term in TERMS:
            try:
                _resolve_uri(term['semantics'], PREFIX_MAP)
            except ValueError as exc:
                raise CommandError(f'TERMS validation error: {exc}') from exc

        # 2. All term_keys in BINDINGS must exist in TERMS.
        known_keys = {t['term_key'] for t in TERMS}
        for binding in BINDINGS:
            if binding['term_key'] not in known_keys:
                raise CommandError(
                    f'BINDINGS validation error: term_key "{binding["term_key"]}" '
                    f'(table={binding["table_name"]}, column={binding["column_name"]}) '
                    f'does not exist in TERMS.'
                )

        # 3. No duplicate (table_name, column_name) in BINDINGS.
        seen: set[tuple[str, str | None]] = set()
        for binding in BINDINGS:
            key = (binding['table_name'], binding['column_name'])
            if key in seen:
                raise CommandError(
                    f'BINDINGS validation error: duplicate binding key '
                    f'table_name="{key[0]}", column_name="{key[1]}".'
                )
            seen.add(key)

        self.stdout.write(self.style.SUCCESS('  Validation passed.'))

    # ── Phase 1: SchemaVersion ────────────────────────────────────────────────

    def _seed_version(self) -> SchemaVersion:
        no_active = not SchemaVersion.objects.filter(is_active=True).exists()
        version, created = SchemaVersion.objects.update_or_create(
            slug=VERSION_SLUG,
            defaults={
                'label': VERSION_LABEL,
                'is_active': True if no_active else SchemaVersion.objects.filter(
                    slug=VERSION_SLUG
                ).values_list('is_active', flat=True).first() or False,
            },
        )
        action = 'Created' if created else 'Updated'
        self.stdout.write(f'  {action} SchemaVersion: {version}')
        return version

    # ── Phase 2: SchemaPrefix ─────────────────────────────────────────────────

    def _seed_prefixes(self, version: SchemaVersion) -> None:
        created_count = updated_count = 0
        for prefix, base_uri in PREFIX_MAP.items():
            _, created = SchemaPrefix.objects.update_or_create(
                schema_version=version,
                prefix=prefix,
                defaults={'base_uri': base_uri},
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
        self.stdout.write(
            f'  SchemaPrefix: {created_count} created, {updated_count} updated '
            f'({len(PREFIX_MAP)} total prefixes).'
        )

    # ── Phase 3: SchemaTerm ───────────────────────────────────────────────────

    def _seed_terms(self, version: SchemaVersion) -> dict[str, SchemaTerm]:
        """Upsert all terms and return a {term_key: SchemaTerm} map."""
        created_count = updated_count = 0
        term_map: dict[str, SchemaTerm] = {}

        for term_def in TERMS:
            pfx, local_name, uri = _resolve_uri(term_def['semantics'], PREFIX_MAP)
            obj, created = SchemaTerm.objects.update_or_create(
                schema_version=version,
                term_key=term_def['term_key'],
                defaults={
                    'semantics': term_def['semantics'],
                    'prefix': pfx,
                    'local_name': local_name,
                    'uri': uri,
                    'base_label_en': term_def['base_label_en'],
                    'base_description_en': term_def['base_description_en'],
                    'requirement': term_def.get('requirement', SchemaTerm.REQUIREMENT_OPTIONAL),
                    'levels': term_def.get('levels', []),
                    'display_order': term_def.get('display_order', 0),
                },
            )
            term_map[term_def['term_key']] = obj
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            f'  SchemaTerm: {created_count} created, {updated_count} updated '
            f'({len(TERMS)} total terms).'
        )
        return term_map

    # ── Phase 4: SchemaFieldBinding ───────────────────────────────────────────

    def _seed_bindings(self, version: SchemaVersion, term_map: dict[str, SchemaTerm]) -> None:
        created_count = updated_count = 0

        for binding_def in BINDINGS:
            term = term_map[binding_def['term_key']]
            _, created = SchemaFieldBinding.objects.update_or_create(
                schema_version=version,
                table_name=binding_def['table_name'],
                column_name=binding_def['column_name'],
                defaults={
                    'schema_term': term,
                    'column_type': binding_def.get('column_type'),
                    'ref_table': binding_def.get('ref_table'),
                    'label_en': binding_def['label_en'],
                    'description_en': binding_def['description_en'],
                    'is_entity': binding_def.get('is_entity', False),
                    'display_order': binding_def.get('display_order', 0),
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            f'  SchemaFieldBinding: {created_count} created, {updated_count} updated '
            f'({len(BINDINGS)} total bindings).'
        )
