"""
Tests for the warehouse application â€” Local Metadata HealthDCAT-AP Profile.

All warehouse models are managed=False (pre-existing metadata_db tables).
Tests verify model structure, __str__, and Meta without DB writes.
"""

from django.test import TestCase

from .models import Agent, Attribute, Catalog, ContactPoint, Dataset, Distribution


class ContactPointModelTest(TestCase):
    """Tests for the ContactPoint model."""

    databases = {'default', 'auth_db'}

    def test_str_with_email(self):
        obj = ContactPoint(email='test@example.com')
        self.assertEqual(str(obj), 'test@example.com')

    def test_str_with_page(self):
        obj = ContactPoint(contact_page='https://example.com/contact')
        self.assertEqual(str(obj), 'https://example.com/contact')

    def test_meta_managed_false(self):
        self.assertFalse(ContactPoint._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(ContactPoint._meta.db_table, 'metadata"."lm_contact_point')


class AgentModelTest(TestCase):
    """Tests for the Agent model."""

    databases = {'default', 'auth_db'}

    def test_str(self):
        obj = Agent(name='Hospital Publisher')
        self.assertEqual(str(obj), 'Hospital Publisher')

    def test_meta_managed_false(self):
        self.assertFalse(Agent._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(Agent._meta.db_table, 'metadata"."lm_agent')


class CatalogModelTest(TestCase):
    """Tests for the Catalog model."""

    databases = {'default', 'auth_db'}

    def test_str_with_title(self):
        obj = Catalog(name='cat1', title='Hospital Catalogue')
        self.assertEqual(str(obj), 'Hospital Catalogue')

    def test_str_fallback_to_name(self):
        obj = Catalog(name='cat1', title='')
        self.assertEqual(str(obj), 'cat1')

    def test_meta_managed_false(self):
        self.assertFalse(Catalog._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(Catalog._meta.db_table, 'metadata"."lm_catalog')


class DatasetModelTest(TestCase):
    """Tests for the Dataset model."""

    databases = {'default', 'auth_db'}

    def test_str_with_title(self):
        obj = Dataset(name='ds1', title='Patient Dataset')
        self.assertEqual(str(obj), 'Patient Dataset')

    def test_str_fallback_to_name(self):
        obj = Dataset(name='ds1', title='')
        self.assertEqual(str(obj), 'ds1')

    def test_meta_managed_false(self):
        self.assertFalse(Dataset._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(Dataset._meta.db_table, 'metadata"."lm_dataset')

    def test_mandatory_fields_present(self):
        """access_rights, applicable_legislation, health_category must not allow blank."""
        for field_name in ('access_rights', 'applicable_legislation', 'health_category'):
            field = Dataset._meta.get_field(field_name)
            self.assertFalse(field.blank, msg=f'{field_name} should have blank=False')


class DistributionModelTest(TestCase):
    """Tests for the Distribution model."""

    databases = {'default', 'auth_db'}

    def test_str_with_title(self):
        obj = Distribution(name='dist1', title='CSV Export')
        self.assertEqual(str(obj), 'CSV Export')

    def test_str_fallback_to_name(self):
        obj = Distribution(name='dist1', title='')
        self.assertEqual(str(obj), 'dist1')

    def test_db_layer_field_nullable(self):
        field = Distribution._meta.get_field('db_layer')
        self.assertTrue(field.null)
        self.assertTrue(field.blank)

    def test_meta_managed_false(self):
        self.assertFalse(Distribution._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(Distribution._meta.db_table, 'metadata"."lm_distribution')

    def test_mandatory_fields_present(self):
        for field_name in ('access_url', 'applicable_legislation'):
            field = Distribution._meta.get_field(field_name)
            self.assertFalse(field.blank, msg=f'{field_name} should have blank=False')


class AttributeModelTest(TestCase):
    """Tests for the Attribute model."""

    databases = {'default', 'auth_db'}

    def test_str_with_title(self):
        obj = Attribute(name='attr1', title='Patient ID')
        self.assertEqual(str(obj), 'Patient ID')

    def test_str_fallback_to_name(self):
        obj = Attribute(name='attr1', title='')
        self.assertEqual(str(obj), 'attr1')

    def test_meta_managed_false(self):
        self.assertFalse(Attribute._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(Attribute._meta.db_table, 'metadata"."lm_attribute')

    def test_meta_ordering(self):
        self.assertEqual(Attribute._meta.ordering, ['var_order', 'name'])

