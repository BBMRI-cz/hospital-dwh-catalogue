"""
Schema Registry  Tests
========================

Tests for the in-memory registry loader (schema_registry.registry) and the
public service layer (schema_registry.services).

No database is involved.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings

from schema_registry.registry import _load, invalidate_cache

# Absolute path to the release-6 directory inside the submodule.
_RELEASE_6 = settings.BASE_DIR / 'health_dcat_ap' / 'public' / 'releases' / 'release-6'


class RegistryParserTest(TestCase):
    """Tests for the SHACL + cardinality-JSON parser (schema_registry.registry)."""

    def setUp(self) -> None:
        invalidate_cache()

    def tearDown(self) -> None:
        invalidate_cache()

    def _load_release6(self) -> dict:
        term_dict, _prefix_map = _load(_RELEASE_6)
        return term_dict

    #  Basic structure

    def test_returns_non_empty_dict(self) -> None:
        registry = self._load_release6()
        self.assertIsInstance(registry, dict)
        self.assertGreater(len(registry), 0)

    def test_keys_are_prefixed_strings(self) -> None:
        registry = self._load_release6()
        for key in registry:
            self.assertIn(':', key, f'Key "{key}" is not in prefix:local form')

    def test_each_entry_has_required_fields(self) -> None:
        registry = self._load_release6()
        required_fields = {
            'prefix',
            'local_name',
            'uri',
            'requirement',
            'cardinality',
            'label',
            'description',
        }
        for key, entry in registry.items():
            with self.subTest(semantics=key):
                self.assertEqual(set(entry.keys()), required_fields)

    #  Requirement values

    def test_requirement_values_are_valid(self) -> None:
        valid = {'mandatory', 'recommended', 'optional', 'deprecated'}
        registry = self._load_release6()
        for key, entry in registry.items():
            with self.subTest(semantics=key):
                self.assertIn(entry['requirement'], valid)

    def test_has_mandatory_terms(self) -> None:
        registry = self._load_release6()
        mandatory = [k for k, v in registry.items() if v['requirement'] == 'mandatory']
        self.assertGreater(len(mandatory), 0)

    #  Known base DCAT-AP terms

    def test_dct_title_present(self) -> None:
        registry = self._load_release6()
        self.assertIn('dct:title', registry)
        entry = registry['dct:title']
        self.assertEqual(entry['prefix'], 'dct')
        self.assertEqual(entry['local_name'], 'title')
        self.assertIn('purl.org/dc/terms', entry['uri'])

    def test_dct_description_present(self) -> None:
        registry = self._load_release6()
        self.assertIn('dct:description', registry)

    def test_dcat_keyword_present(self) -> None:
        registry = self._load_release6()
        self.assertIn('dcat:keyword', registry)

    def test_dct_publisher_is_recommended(self) -> None:
        """JSON overrides SHACL: publisher is Recommended at dataset level."""
        registry = self._load_release6()
        self.assertIn('dct:publisher', registry)
        self.assertEqual(registry['dct:publisher']['requirement'], 'recommended')

    #  URI consistency

    def test_uri_matches_prefix_and_local_name(self) -> None:
        registry = self._load_release6()
        for key, entry in registry.items():
            with self.subTest(semantics=key):
                self.assertTrue(entry['uri'].endswith(entry['local_name']))

    def test_no_empty_uris(self) -> None:
        registry = self._load_release6()
        for key, entry in registry.items():
            with self.subTest(semantics=key):
                self.assertTrue(entry['uri'], f'Empty URI for "{key}"')

    #  HealthDCAT-AP extension terms

    def test_healthdcat_healthcategory_present(self) -> None:
        registry = self._load_release6()
        self.assertIn('healthdcatap:healthCategory', registry)
        entry = registry['healthdcatap:healthCategory']
        self.assertEqual(entry['prefix'], 'healthdcatap')
        self.assertEqual(entry['local_name'], 'healthCategory')
        self.assertIn('healthdataportal.eu', entry['uri'])
        self.assertEqual(entry['requirement'], 'mandatory')

    def test_healthdcat_hdab_present(self) -> None:
        registry = self._load_release6()
        self.assertIn('healthdcatap:hdab', registry)
        entry = registry['healthdcatap:hdab']
        self.assertEqual(entry['requirement'], 'mandatory')

    #  Namespace prefix map

    def test_namespace_prefixes_include_healthdcat_specific(self) -> None:
        """
        Prefixes declared only in html/shacl/public-shapes.ttl (not in the base
        DCAT-AP SHACL TTL) must be present in the returned prefix map.
        """
        from schema_registry.registry import get_namespace_prefixes

        prefixes = get_namespace_prefixes(_RELEASE_6)
        for expected in ('healthdcatap', 'geodcatap', 'dcatap', 'dpv', 'org', 'csvw'):
            with self.subTest(prefix=expected):
                self.assertIn(expected, prefixes, f'Prefix "{expected}" missing from namespace map')
                self.assertTrue(prefixes[expected].startswith('http'))

    #  Edge cases

    def test_missing_release_dir_returns_empty_dict(self) -> None:
        term_dict, prefix_map = _load(Path('/nonexistent/path/release-99'))
        self.assertEqual(term_dict, {})
        self.assertEqual(prefix_map, {})

    def test_result_is_json_serialisable(self) -> None:
        registry = self._load_release6()
        serialised = json.dumps(registry)
        self.assertIsInstance(serialised, str)

    #  Cardinality

    def test_cardinality_set_for_json_matched_terms(self) -> None:
        """Terms matched in the cardinality JSON must have a non-empty cardinality."""
        registry = self._load_release6()
        self.assertNotEqual(registry['dct:title']['cardinality'], '')
        self.assertNotEqual(registry['healthdcatap:healthCategory']['cardinality'], '')

    def test_cardinality_format(self) -> None:
        """Cardinality values must follow the 'min..max' pattern."""
        registry = self._load_release6()
        for key, entry in registry.items():
            card = entry['cardinality']
            if card:
                with self.subTest(semantics=key):
                    self.assertRegex(card, r'^\d+\.\.([\d*]+)$')

    #  Requirement upgrade from JSON

    def test_dcat_keyword_is_recommended(self) -> None:
        """JSON upgrades dcat:keyword from SHACL 'optional' to 'recommended'."""
        registry = self._load_release6()
        self.assertIn('dcat:keyword', registry)
        self.assertEqual(registry['dcat:keyword']['requirement'], 'recommended')


class RegistryCacheTest(TestCase):
    """Tests for the module-level lazy cache in schema_registry.registry."""

    def setUp(self) -> None:
        invalidate_cache()

    def tearDown(self) -> None:
        invalidate_cache()

    def test_get_registry_caches_result(self) -> None:
        from schema_registry.registry import get_registry

        first = get_registry(_RELEASE_6)
        second = get_registry(_RELEASE_6)
        self.assertIs(first, second)

    def test_invalidate_clears_cache(self) -> None:
        from schema_registry.registry import get_registry

        first = get_registry(_RELEASE_6)
        invalidate_cache()
        second = get_registry(_RELEASE_6)
        # Should be a fresh dict (different object)
        self.assertIsNot(first, second)

    def test_cache_keyed_by_path(self) -> None:
        """Different release_dir values get independent cache entries."""
        from schema_registry.registry import get_registry

        good = get_registry(_RELEASE_6)
        bad = get_registry(Path('/nonexistent/path/release-99'))
        # The valid path returns data, the missing path returns empty
        self.assertGreater(len(good), 0)
        self.assertEqual(len(bad), 0)
        # Calling the valid path again still returns the cached data (not empty)
        self.assertIs(get_registry(_RELEASE_6), good)


class ServiceLayerTest(TestCase):
    """Tests for the public service API (schema_registry.services)."""

    def setUp(self) -> None:
        invalidate_cache()

    def tearDown(self) -> None:
        invalidate_cache()

    def test_get_schema_dict_returns_dict(self) -> None:
        from schema_registry.services import get_schema_dict

        result = get_schema_dict()
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)

    def test_get_schema_dict_uses_settings_version(self) -> None:
        from schema_registry.services import get_schema_dict

        with override_settings(HEALTH_DCAT_VERSION='release-6'):
            invalidate_cache()
            result = get_schema_dict()
        self.assertIn('dct:title', result)

    def test_get_schema_dict_returns_empty_for_unknown_version(self) -> None:
        from schema_registry.services import get_schema_dict

        with override_settings(HEALTH_DCAT_VERSION='release-999'):
            invalidate_cache()
            result = get_schema_dict()
        self.assertEqual(result, {})

    def test_get_context_prefixes_returns_dict(self) -> None:
        from schema_registry.services import get_context_prefixes

        result = get_context_prefixes()
        self.assertIsInstance(result, dict)
        self.assertIn('dct', result)
        self.assertTrue(result['dct'].startswith('http'))
