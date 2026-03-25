"""
Tests for the warehouse application â€” Local Metadata HealthDCAT-AP Profile.

All warehouse models are managed=False (pre-existing metadata_db tables).
Tests verify model structure, __str__, and Meta without DB writes.
"""

from django.test import TestCase

from .models import Agent, Catalog, Column, ContactPoint, Dataset, Distribution, Table


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

    def test_mandatory_fields_present(self):
        """title and description are mandatory per HealthDCAT-AP v6."""
        for field_name in ('title', 'description', 'applicable_legislation'):
            field = Catalog._meta.get_field(field_name)
            self.assertFalse(field.blank, msg=f'{field_name} should have blank=False')


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
        """Mandatory HealthDCAT-AP v6 fields must not allow blank."""
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


class TableModelTest(TestCase):
    """Tests for the Table model (csvw:Table)."""

    databases = {'default', 'auth_db'}

    def test_str_with_title(self):
        obj = Table(name='TBL_PAT_RAW', title='Raw patient table')
        self.assertEqual(str(obj), 'Raw patient table')

    def test_str_fallback_to_name(self):
        obj = Table(name='TBL_PAT_RAW', title=None)
        self.assertEqual(str(obj), 'TBL_PAT_RAW')

    def test_meta_managed_false(self):
        self.assertFalse(Table._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(Table._meta.db_table, 'metadata"."lm_table')

    def test_meta_ordering(self):
        self.assertEqual(Table._meta.ordering, ['name'])

    def test_url_mandatory(self):
        field = Table._meta.get_field('url')
        self.assertFalse(field.null)
        self.assertFalse(field.blank)


class ColumnModelTest(TestCase):
    """Tests for the Column model (csvw:Column)."""

    databases = {'default', 'auth_db'}

    def test_str_with_title(self):
        obj = Column(name='COL_PAT_ID', title='ID pacienta')
        self.assertEqual(str(obj), 'ID pacienta')

    def test_str_fallback_to_name(self):
        obj = Column(name='COL_PAT_ID', title='')
        self.assertEqual(str(obj), 'COL_PAT_ID')

    def test_meta_managed_false(self):
        self.assertFalse(Column._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(Column._meta.db_table, 'metadata"."lm_column')

    def test_meta_ordering(self):
        self.assertEqual(Column._meta.ordering, ['var_order', 'name'])

    def test_mandatory_fields_not_nullable(self):
        """title, description, datatype are mandatory and must not allow null/blank."""
        for field_name in ('title', 'description', 'datatype'):
            field = Column._meta.get_field(field_name)
            self.assertFalse(
                getattr(field, 'null', False), msg=f'{field_name} should not be null=True'
            )
            self.assertFalse(field.blank, msg=f'{field_name} should have blank=False')

    def test_optional_fields_nullable(self):
        """All metadata helper fields must be nullable."""
        for field_name in (
            'property_url',
            'var_order',
            'key_db',
            'type_r',
            'definition_ddl',
            'definition_pk_pom1',
            'definition_pk_pom2',
            'definition_pk',
        ):
            field = Column._meta.get_field(field_name)
            self.assertTrue(field.null, msg=f'{field_name} should allow null')
            self.assertTrue(field.blank, msg=f'{field_name} should allow blank')
