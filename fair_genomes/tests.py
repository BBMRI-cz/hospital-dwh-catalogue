"""
Tests for the fair_genomes application — HealthDCAT-AP Profile.

FAIR Genomes models are managed=True (Django creates tables in fair_genomes_db).
Model tests do not require DB writes; service tests mock HTTP so no live API
calls are made.
"""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

from .models import Agent, Catalog, ContactPoint, Dataset, Distribution, StatDefinition, StatResult
from .services.fair_genomes_service import (
    FairGenomesAPIException,
    FairGenomesService,
    _resolve_graph_predicate_uri,
    _uri_local_name,
)


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


class GraphPredicateResolutionTest(SimpleTestCase):
    """Tests for resolving RDF predicates from the parsed graph itself."""

    def test_uri_local_name_handles_hash_namespaces(self):
        self.assertEqual(
            _uri_local_name('http://healthdataportal.eu/ns/health#healthCategory'),
            'healthCategory',
        )

    def test_uri_local_name_handles_path_namespaces(self):
        self.assertEqual(
            _uri_local_name('http://data.europa.eu/r5r/applicableLegislation'),
            'applicableLegislation',
        )

    def test_resolve_graph_predicate_uri_returns_unique_match(self):
        predicate_uris = {
            'https://example.org/ext/applicableLegislation',
            'https://example.org/health#healthCategory',
        }

        self.assertEqual(
            _resolve_graph_predicate_uri(predicate_uris, 'applicableLegislation'),
            'https://example.org/ext/applicableLegislation',
        )
        self.assertEqual(
            _resolve_graph_predicate_uri(predicate_uris, 'healthCategory'),
            'https://example.org/health#healthCategory',
        )

    def test_resolve_graph_predicate_uri_returns_none_for_missing_name(self):
        predicate_uris = {'https://example.org/ext/somethingElse'}

        self.assertIsNone(_resolve_graph_predicate_uri(predicate_uris, 'healthCategory'))

    def test_resolve_graph_predicate_uri_returns_none_for_ambiguous_name(self):
        predicate_uris = {
            'https://example.org/one/healthCategory',
            'https://example.org/two#healthCategory',
        }

        self.assertIsNone(_resolve_graph_predicate_uri(predicate_uris, 'healthCategory'))


class TableModelTest(TestCase):
    """Table model has been removed — this placeholder prevents test discovery issues."""

    pass


class ColumnModelTest(TestCase):
    """Column model has been removed — this placeholder prevents test discovery issues."""

    pass


class StatResultModelTest(TestCase):
    """Tests for the StatResult model."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def test_meta_managed_true(self):
        self.assertTrue(StatResult._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(StatResult._meta.db_table, 'fair_genomes_stat_result')

    def test_unique_together(self):
        constraint = list(StatResult._meta.unique_together)
        self.assertIn(('table_name', 'column_name'), constraint)

    def test_create_and_retrieve(self):
        StatResult.objects.using('fair_genomes_db').create(
            table_name='sequencing',
            column_name='sequencinginstrumentmodel',
            distribution={'MiSeq': 42, 'NovaSeq': 10},
        )
        sr = StatResult.objects.using('fair_genomes_db').get(
            table_name='sequencing',
            column_name='sequencinginstrumentmodel',
        )
        self.assertEqual(sr.distribution, {'MiSeq': 42, 'NovaSeq': 10})


class SyncStatsTest(TestCase):
    """Tests for FairGenomesService._sync_stats() — HTTP is always mocked."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    STAT_DEFS = [
        ('sequencing', 'sequencinginstrumentmodel'),
        ('sequencing', 'librarypreparationkit'),
    ]

    def setUp(self):
        """Create a Distribution and two StatDefinition rows for testing."""
        from .models import Agent, Catalog, ContactPoint, Dataset, Distribution, StatDefinition

        cp, _ = ContactPoint.objects.using('fair_genomes_db').get_or_create(
            email='test@example.org',
        )
        agent, _ = Agent.objects.using('fair_genomes_db').get_or_create(
            name='test-agent',
        )
        Catalog.objects.using('fair_genomes_db').get_or_create(
            name='test-cat',
            defaults={'title': 't', 'description': 'd', 'applicable_legislation': 'http://x'},
        )
        Dataset.objects.using('fair_genomes_db').get_or_create(
            name='test-ds',
            defaults={
                'title': 't',
                'description': 'd',
                'access_rights': 'public',
                'applicable_legislation': 'http://x',
                'health_category': 'genomics',
                'catalog_id': 'test-cat',
                'contact_point': cp,
                'hdab': agent,
            },
        )
        Distribution.objects.using('fair_genomes_db').get_or_create(
            name='DIST_TEST',
            defaults={
                'title': 'Test Distribution',
                'access_url': 'http://example.com',
                'applicable_legislation': 'http://x',
                'dataset_name_id': 'test-ds',
            },
        )
        for i, (table, col) in enumerate(self.STAT_DEFS):
            StatDefinition.objects.using('fair_genomes_db').get_or_create(
                distribution_id='DIST_TEST',
                molgenis_table=table,
                molgenis_column=col,
                defaults={'sort_order': i, 'is_active': True},
            )

    def _make_groupby_response(self, table: str, column: str, dist: dict) -> MagicMock:
        """Return a mock requests.Response for a successful groupBy query."""
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        table_cap = table[0].upper() + table[1:]
        rows = [{'count': count, column: {'value': value}} for value, count in dist.items()]
        resp.json.return_value = {'data': {f'{table_cap}_groupBy': rows}}
        return resp

    @patch('fair_genomes.services.fair_genomes_service.requests.post')
    def test_sync_stats_success(self, mock_post):
        # Each stat def gets its own mock response; only the first needs real data.
        n = len(self.STAT_DEFS)
        first_resp = self._make_groupby_response(
            'sequencing', 'sequencinginstrumentmodel', {'MiSeq': 17, 'NovaSeq': 5}
        )
        # Remaining defs receive a valid-but-empty groupBy response.
        empty_resp = MagicMock()
        empty_resp.raise_for_status.return_value = None
        empty_resp.json.return_value = {'data': {}}
        mock_post.side_effect = [first_resp] + [empty_resp] * (n - 1)

        svc = FairGenomesService(api_url='http://mock/graphql', api_token='tok')
        report = svc._sync_stats()

        self.assertEqual(report['updated'], n)
        self.assertEqual(report['failed'], 0)
        self.assertEqual(report['errors'], [])

        sr = StatResult.objects.using('fair_genomes_db').get(
            table_name='sequencing',
            column_name='sequencinginstrumentmodel',
        )
        self.assertEqual(sr.distribution, {'MiSeq': 17, 'NovaSeq': 5})

    @patch('fair_genomes.services.fair_genomes_service.requests.post')
    def test_sync_stats_http_error(self, mock_post):
        import requests as req_lib

        mock_post.side_effect = req_lib.RequestException('connection refused')

        svc = FairGenomesService(api_url='http://mock/graphql', api_token='tok')
        report = svc._sync_stats()

        n = len(self.STAT_DEFS)
        self.assertEqual(report['updated'], 0)
        self.assertEqual(report['failed'], n)
        self.assertEqual(len(report['errors']), n)

    @patch('fair_genomes.services.fair_genomes_service.requests.post')
    def test_sync_stats_graphql_error_response(self, mock_post):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {'errors': [{'message': 'unknown field'}]}
        mock_post.return_value = resp

        svc = FairGenomesService(api_url='http://mock/graphql', api_token='tok')
        report = svc._sync_stats()

        n = len(self.STAT_DEFS)
        self.assertEqual(report['failed'], n)
        self.assertEqual(len(report['errors']), n)
        self.assertIn('GraphQL errors', report['errors'][0])


class StatDefinitionModelTest(TestCase):
    """Tests for the StatDefinition model."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def test_meta_managed_true(self):
        self.assertTrue(StatDefinition._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(StatDefinition._meta.db_table, 'fair_genomes_stat_definition')

    def test_unique_together(self):
        constraint = list(StatDefinition._meta.unique_together)
        self.assertIn(('distribution', 'molgenis_table', 'molgenis_column'), constraint)

    def test_chart_label_uses_display_label(self):
        sd = StatDefinition(molgenis_table='seq', molgenis_column='col', display_label='My Label')
        self.assertEqual(sd.chart_label, 'My Label')

    def test_chart_label_falls_back_to_table_column(self):
        sd = StatDefinition(molgenis_table='seq', molgenis_column='col', display_label='')
        self.assertEqual(sd.chart_label, 'seq.col')

    def test_str_representation(self):
        sd = StatDefinition(
            molgenis_table='seq',
            molgenis_column='col',
            display_label='',
            distribution_id='DIST_X',
        )
        self.assertEqual(str(sd), 'seq.col → DIST_X')
