"""
Tests for the fair_genomes application â€” HealthDCAT-AP Profile.

FAIR Genomes models are managed=True (Django creates tables in fair_genomes_db).
Model tests do not require DB writes; service tests check the sync stub.
"""

from django.test import TestCase

from .models import Agent, Catalog, ContactPoint, Dataset, Distribution
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
        for field_name in ('access_rights', 'applicable_legislation', 'health_category'):
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
    """Tests for the FairGenomesService stub."""

    databases = {'default', 'auth_db'}

    def test_sync_returns_not_implemented(self):
        """sync() stub must return the expected sentinel dict."""
        with FairGenomesService() as svc:
            result = svc.sync()
        self.assertEqual(result, {'status': 'not_implemented'})

    def test_context_manager(self):
        """Service can be used as a context manager."""
        with FairGenomesService(api_url='http://test', api_token='tok') as svc:
            self.assertIsInstance(svc, FairGenomesService)

    def test_close_no_error(self):
        svc = FairGenomesService()
        svc.close()  # must not raise

    def test_exception_class_exists(self):
        self.assertTrue(issubclass(FairGenomesAPIException, Exception))

