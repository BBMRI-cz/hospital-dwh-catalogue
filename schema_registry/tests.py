"""
Schema Registry — Unit Tests
=============================

Coverage:
  SeedCommandTest      — management command idempotency, row counts, active flag
  ServiceLayerTest     — all service functions, translation fallback
  DefinitionsTest      — pure-Python validation of v6_definitions (no DB)
"""

from __future__ import annotations

from django.core.management import call_command
from django.test import TestCase

from schema_registry.models import SchemaFieldBinding, SchemaTerm, SchemaVersion
from schema_registry.v6_definitions import BINDINGS, PREFIX_MAP, TERMS


# ── Helper ────────────────────────────────────────────────────────────────────


def _seed() -> None:
    """Run seed_schema_v6 without printing to stdout."""
    call_command('seed_schema_v6', verbosity=0)


# ── Definition sanity checks (no DB required) ─────────────────────────────────


class DefinitionsTest(TestCase):
    """Validate that v6_definitions.py is internally consistent."""

    def test_no_duplicate_binding_keys(self) -> None:
        seen: set[tuple[str, str | None]] = set()
        for b in BINDINGS:
            key = (b['table_name'], b['column_name'])
            self.assertNotIn(key, seen, f'Duplicate binding: {key}')
            seen.add(key)

    def test_all_binding_term_keys_exist_in_terms(self) -> None:
        known = {t['term_key'] for t in TERMS}
        for b in BINDINGS:
            self.assertIn(
                b['term_key'],
                known,
                f'Binding term_key "{b["term_key"]}" for {b["table_name"]}.{b["column_name"]} '
                f'not found in TERMS.',
            )

    def test_all_semantics_have_resolvable_uris(self) -> None:
        """Every semantics value must be resolvable to a non-empty URI."""
        for term in TERMS:
            semantics = term['semantics']
            self.assertIn(':', semantics, f'semantics "{semantics}" has no colon.')
            prefix, local_name = semantics.split(':', 1)
            self.assertIn(prefix, PREFIX_MAP, f'Prefix "{prefix}" not in PREFIX_MAP.')
            base = PREFIX_MAP[prefix]
            self.assertTrue(base, f'PREFIX_MAP["{prefix}"] is empty.')
            uri = base + local_name
            self.assertTrue(uri, f'Resolved URI for "{semantics}" is empty.')

    def test_entity_bindings_have_null_column(self) -> None:
        for b in BINDINGS:
            if b.get('is_entity'):
                self.assertIsNone(b['column_name'], f'Entity binding for {b["table_name"]} has non-null column_name.')
                self.assertIsNone(b['column_type'], f'Entity binding for {b["table_name"]} has non-null column_type.')

    def test_term_keys_unique_in_terms(self) -> None:
        keys = [t['term_key'] for t in TERMS]
        self.assertEqual(len(keys), len(set(keys)), 'Duplicate term_keys found in TERMS.')


# ── Management command ─────────────────────────────────────────────────────────


class SeedCommandTest(TestCase):
    """Tests for seed_schema_v6 management command."""

    def test_seed_creates_version(self) -> None:
        _seed()
        self.assertTrue(SchemaVersion.objects.filter(slug='v6').exists())

    def test_seed_sets_active(self) -> None:
        _seed()
        version = SchemaVersion.objects.get(slug='v6')
        self.assertTrue(version.is_active)

    def test_seed_creates_expected_term_count(self) -> None:
        _seed()
        version = SchemaVersion.objects.get(slug='v6')
        self.assertEqual(SchemaTerm.objects.filter(schema_version=version).count(), len(TERMS))

    def test_seed_creates_expected_binding_count(self) -> None:
        _seed()
        version = SchemaVersion.objects.get(slug='v6')
        self.assertEqual(
            SchemaFieldBinding.objects.filter(schema_version=version).count(), len(BINDINGS)
        )

    def test_seed_is_idempotent(self) -> None:
        """Running seed twice must not create duplicate rows."""
        _seed()
        _seed()
        version = SchemaVersion.objects.get(slug='v6')
        self.assertEqual(SchemaVersion.objects.count(), 1)
        self.assertEqual(SchemaTerm.objects.filter(schema_version=version).count(), len(TERMS))
        self.assertEqual(
            SchemaFieldBinding.objects.filter(schema_version=version).count(), len(BINDINGS)
        )

    def test_seed_creates_prefix_rows(self) -> None:
        _seed()
        version = SchemaVersion.objects.get(slug='v6')
        self.assertEqual(version.prefixes.count(), len(PREFIX_MAP))

    def test_dataset_binding_count(self) -> None:
        _seed()
        expected = sum(1 for b in BINDINGS if b['table_name'] == 'Dataset')
        from schema_registry.services import list_bindings
        self.assertEqual(len(list_bindings(table='Dataset')), expected)


# ── Service layer ─────────────────────────────────────────────────────────────


class ServiceLayerTest(TestCase):
    """Tests for schema_registry.services public API."""

    def setUp(self) -> None:
        _seed()

    def test_get_registry_version_returns_active(self) -> None:
        from schema_registry.services import get_registry_version
        version = get_registry_version()
        self.assertEqual(version.slug, 'v6')
        self.assertTrue(version.is_active)

    def test_get_registry_version_raises_when_none_active(self) -> None:
        from schema_registry.services import get_registry_version
        SchemaVersion.objects.update(is_active=False)
        with self.assertRaises(SchemaVersion.DoesNotExist):
            get_registry_version()

    def test_list_terms_all(self) -> None:
        from schema_registry.services import list_terms
        terms = list_terms()
        self.assertEqual(len(terms), len(TERMS))

    def test_list_terms_by_level(self) -> None:
        from schema_registry.services import list_terms
        dataset_terms = list_terms(level='Dataset')
        # Every term in the result must have 'Dataset' in its levels.
        for t in dataset_terms:
            self.assertIn('Dataset', t.levels)
        # Sanity: there should be at least a few dataset terms.
        self.assertGreater(len(dataset_terms), 5)

    def test_get_term_returns_correct_semantics(self) -> None:
        from schema_registry.services import get_term
        term = get_term('identifier')
        self.assertEqual(term.semantics, 'dct:identifier')
        self.assertIn('http://purl.org/dc/terms/', term.uri)

    def test_get_term_raises_for_unknown_key(self) -> None:
        from schema_registry.services import get_term
        with self.assertRaises(SchemaTerm.DoesNotExist):
            get_term('nonexistent_term_key')

    def test_list_bindings_all(self) -> None:
        from schema_registry.services import list_bindings
        bindings = list_bindings()
        self.assertEqual(len(bindings), len(BINDINGS))

    def test_list_bindings_filtered_by_table(self) -> None:
        from schema_registry.services import list_bindings
        bindings = list_bindings(table='Catalog')
        self.assertTrue(all(b.table_name == 'Catalog' for b in bindings))
        expected = sum(1 for b in BINDINGS if b['table_name'] == 'Catalog')
        self.assertEqual(len(bindings), expected)

    def test_get_binding_entity_row(self) -> None:
        from schema_registry.services import get_binding
        binding = get_binding('Dataset')
        self.assertTrue(binding.is_entity)
        self.assertIsNone(binding.column_name)

    def test_get_binding_column_row(self) -> None:
        from schema_registry.services import get_binding
        binding = get_binding('Dataset', 'name')
        self.assertFalse(binding.is_entity)
        self.assertEqual(binding.column_name, 'name')
        self.assertEqual(binding.column_type, 'string')

    def test_describe_term_returns_expected_keys(self) -> None:
        from schema_registry.services import describe_term
        result = describe_term('identifier')
        expected_keys = {'term_key', 'semantics', 'prefixed_name', 'uri', 'requirement', 'label', 'description', 'levels'}
        self.assertEqual(set(result.keys()), expected_keys)

    def test_describe_term_english_fallback(self) -> None:
        """When no PO translation exists the stored English text is returned."""
        from schema_registry.services import describe_term
        result = describe_term('identifier', lang='cs')
        term = SchemaTerm.objects.get(term_key='identifier', schema_version__slug='v6')
        # Czech msgstr is empty in the PO so fallback to EN base text applies.
        # (The fallback is triggered because gettext returns the msgid unchanged.)
        # Either the DB English base OR a real Czech translation must be returned
        # — not the bare msgid.
        self.assertNotEqual(result['label'], 'schema.term.identifier.label')
        self.assertNotEqual(result['description'], 'schema.term.identifier.description')
        # When Czech is empty, we expect the English base text.
        self.assertEqual(result['label'], term.base_label_en)

    def test_describe_binding_returns_expected_keys(self) -> None:
        from schema_registry.services import describe_binding
        result = describe_binding('Dataset', 'title')
        expected_keys = {'table', 'column', 'type', 'ref_table', 'term_key', 'semantics', 'uri', 'label', 'description', 'is_entity'}
        self.assertEqual(set(result.keys()), expected_keys)

    def test_describe_binding_entity_row(self) -> None:
        from schema_registry.services import describe_binding
        result = describe_binding('Agent')
        self.assertTrue(result['is_entity'])
        self.assertIsNone(result['column'])

    def test_export_registry_snapshot_structure(self) -> None:
        from schema_registry.services import export_registry_snapshot
        snapshot = export_registry_snapshot()
        self.assertIn('schema_version', snapshot)
        self.assertIn('prefixes', snapshot)
        self.assertIn('terms', snapshot)
        self.assertIn('bindings', snapshot)
        self.assertEqual(snapshot['schema_version']['slug'], 'v6')
        self.assertEqual(len(snapshot['terms']), len(TERMS))
        self.assertEqual(len(snapshot['bindings']), len(BINDINGS))
        self.assertEqual(len(snapshot['prefixes']), len(PREFIX_MAP))

    def test_export_snapshot_is_json_serialisable(self) -> None:
        import json
        from schema_registry.services import export_registry_snapshot
        snapshot = export_registry_snapshot()
        # Must not raise
        serialised = json.dumps(snapshot)
        self.assertIsInstance(serialised, str)
