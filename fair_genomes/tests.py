"""
Tests for the fair_genomes application — HealthDCAT-AP Profile.

FAIR Genomes models are managed=True (Django creates tables in fair_genomes_db).
Model tests do not require DB writes; service tests mock HTTP so no live API
calls are made.
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from .models import Agent, Catalog, Column, ContactPoint, Dataset, Distribution, StatResult, Table
from .services.fair_genomes_service import FairGenomesAPIException, FairGenomesService


class ContactPointModelTest(TestCase):
    """Tests for the FG ContactPoint model."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def test_str_with_email(self):
        obj = ContactPoint(email='contact@fg.org')
        self.assertEqual(str(obj), 'contact@fg.org')

    def test_meta_managed_true(self):
        self.assertTrue(ContactPoint._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(ContactPoint._meta.db_table, 'fair_genomes_contact_point')


class AgentModelTest(TestCase):
    """Tests for the FG Agent model."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def test_str(self):
        obj = Agent(name='FAIR Genomes Publisher')
        self.assertEqual(str(obj), 'FAIR Genomes Publisher')

    def test_meta_managed_true(self):
        self.assertTrue(Agent._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(Agent._meta.db_table, 'fair_genomes_agent')


class CatalogModelTest(TestCase):
    """Tests for the FG Catalog model."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def test_str_with_title(self):
        obj = Catalog(name='fg-cat', title='FAIR Genomes Catalogue')
        self.assertEqual(str(obj), 'FAIR Genomes Catalogue')

    def test_str_fallback_to_name(self):
        obj = Catalog(name='fg-cat', title='')
        self.assertEqual(str(obj), 'fg-cat')

    def test_meta_managed_true(self):
        self.assertTrue(Catalog._meta.managed)

    def test_mandatory_fields_not_blank(self):
        """title, description and applicable_legislation are mandatory per HealthDCAT-AP v6."""
        for field_name in ('title', 'description', 'applicable_legislation'):
            field = Catalog._meta.get_field(field_name)
            self.assertFalse(field.blank, msg=f'{field_name} should have blank=False')


class DatasetModelTest(TestCase):
    """Tests for the FG Dataset model."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def test_str_with_title(self):
        obj = Dataset(name='fg-ds1', title='FAIR Genomes Dataset')
        self.assertEqual(str(obj), 'FAIR Genomes Dataset')

    def test_str_fallback_to_name(self):
        obj = Dataset(name='fg-ds1', title='')
        self.assertEqual(str(obj), 'fg-ds1')

    def test_meta_managed_true(self):
        self.assertTrue(Dataset._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(Dataset._meta.db_table, 'fair_genomes_dataset')

    def test_mandatory_fields_not_blank(self):
        for field_name in (
            'access_rights',
            'applicable_legislation',
            'health_category',
            'title',
            'description',
        ):
            field = Dataset._meta.get_field(field_name)
            self.assertFalse(field.blank, msg=f'{field_name} should have blank=False')


class DistributionModelTest(TestCase):
    """Tests for the FG Distribution model."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def test_str_with_title(self):
        obj = Distribution(name='fg-dist1', title='FAIR Genomes Distribution')
        self.assertEqual(str(obj), 'FAIR Genomes Distribution')

    def test_str_fallback_to_name(self):
        obj = Distribution(name='fg-dist1', title='')
        self.assertEqual(str(obj), 'fg-dist1')

    def test_meta_managed_true(self):
        self.assertTrue(Distribution._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(Distribution._meta.db_table, 'fair_genomes_distribution')

    def test_mandatory_fields_not_blank(self):
        for field_name in ('access_url', 'applicable_legislation'):
            field = Distribution._meta.get_field(field_name)
            self.assertFalse(field.blank, msg=f'{field_name} should have blank=False')


class FairGenomesServiceTest(TestCase):
    """Tests for the FairGenomesService."""

    databases = {'default', 'auth_db'}

    def test_sync_skips_when_no_urls_configured(self):
        """sync() returns status=skipped when neither URL is explicitly set to ''."""
        # Pass explicit empty strings to bypass settings-fallback
        with FairGenomesService(rdf_url='', api_url='', api_token='') as svc:
            result = svc.sync()
        self.assertEqual(result['status'], 'skipped')
        self.assertIn('reason', result)

    def test_context_manager(self):
        """Service can be used as a context manager."""
        with FairGenomesService(api_url='http://test', api_token='tok') as svc:
            self.assertIsInstance(svc, FairGenomesService)

    def test_close_no_error(self):
        svc = FairGenomesService()
        svc.close()  # must not raise

    def test_exception_class_exists(self):
        self.assertTrue(issubclass(FairGenomesAPIException, Exception))


class TableModelTest(TestCase):
    """Tests for the FG Table model."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def test_str_with_title(self):
        obj = Table(name='sequencing', title='Sequencing')
        self.assertEqual(str(obj), 'Sequencing')

    def test_str_fallback_to_name(self):
        obj = Table(name='sequencing', title='')
        self.assertEqual(str(obj), 'sequencing')

    def test_meta_managed_true(self):
        self.assertTrue(Table._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(Table._meta.db_table, 'fair_genomes_table')


class ColumnModelTest(TestCase):
    """Tests for the FG Column model."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def test_meta_managed_true(self):
        self.assertTrue(Column._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(Column._meta.db_table, 'fair_genomes_column')


class StatResultModelTest(TestCase):
    """Tests for the StatResult model."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def test_meta_managed_true(self):
        self.assertTrue(StatResult._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(StatResult._meta.db_table, 'fair_genomes_stat_result')

    def test_unique_together(self):
        constraint = list(StatResult._meta.unique_together)
        self.assertIn(('table_name', 'column_name', 'filter_value'), constraint)

    def test_create_and_retrieve(self):
        StatResult.objects.using('fair_genomes_db').create(
            table_name='sequencing',
            column_name='sequencinginstrumentmodel',
            filter_value='MiSeq',
            count=42,
        )
        sr = StatResult.objects.using('fair_genomes_db').get(
            table_name='sequencing',
            column_name='sequencinginstrumentmodel',
            filter_value='MiSeq',
        )
        self.assertEqual(sr.count, 42)


class SyncStatsTest(TestCase):
    """Tests for FairGenomesService._sync_stats() — HTTP is always mocked."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def _make_ok_response(self, table: str, count: int) -> MagicMock:
        """Return a mock requests.Response for a successful aggregation query."""
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        # MOLGENIS uses the capitalized table name as the response key
        resp.json.return_value = {'data': {f'{table.capitalize()}_agg': {'count': count}}}
        return resp

    @patch('fair_genomes.services.fair_genomes_service.requests.post')
    def test_sync_stats_success(self, mock_post):
        mock_post.return_value = self._make_ok_response('sequencing', 17)

        svc = FairGenomesService(api_url='http://mock/graphql', api_token='tok')
        report = svc._sync_stats()

        self.assertEqual(report['updated'], 1)
        self.assertEqual(report['failed'], 0)
        self.assertEqual(report['errors'], [])

        sr = StatResult.objects.using('fair_genomes_db').get(
            table_name='sequencing',
            column_name='sequencinginstrumentmodel',
            filter_value='MiSeq',
        )
        self.assertEqual(sr.count, 17)

    @patch('fair_genomes.services.fair_genomes_service.requests.post')
    def test_sync_stats_http_error(self, mock_post):
        import requests as req_lib
        mock_post.side_effect = req_lib.RequestException('connection refused')

        svc = FairGenomesService(api_url='http://mock/graphql', api_token='tok')
        report = svc._sync_stats()

        self.assertEqual(report['updated'], 0)
        self.assertEqual(report['failed'], 1)
        self.assertEqual(len(report['errors']), 1)

    @patch('fair_genomes.services.fair_genomes_service.requests.post')
    def test_sync_stats_graphql_error_response(self, mock_post):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {'errors': [{'message': 'unknown field'}]}
        mock_post.return_value = resp

        svc = FairGenomesService(api_url='http://mock/graphql', api_token='tok')
        report = svc._sync_stats()

        self.assertEqual(report['failed'], 1)
        self.assertIn('GraphQL errors', report['errors'][0])
