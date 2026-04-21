"""
Tests for the catalogue project configuration.

Covers URL routing, views, and database routers.
"""

import importlib
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from .routers import AuthRouter, WarehouseRouter


class LdapSettingsTest(SimpleTestCase):
    def test_ldap_settings_default_login_attr_is_samaccountname(self):
        from .settings.helpers import ldap_settings

        env = {
            'AUTH_LDAP_SERVER_URI': 'ldaps://ldap.example.com:636',
            'AUTH_LDAP_BIND_DN': 'cn=svc,dc=example,dc=com',
            'AUTH_LDAP_BIND_PASSWORD': 'secret',
            'AUTH_LDAP_USER_SEARCH_BASE': 'ou=Users,dc=example,dc=com',
        }

        with patch.dict(os.environ, env, clear=False):
            settings = ldap_settings(mock_ldap=False)

        self.assertEqual(settings['AUTH_LDAP_LOGIN_ATTR'], 'sAMAccountName')
        self.assertEqual(
            settings['AUTH_LDAP_USER_SEARCH_FILTER'],
            '(&(objectClass=user)(!(objectClass=computer))(sAMAccountName=%(user)s))',
        )

    def test_ldap_settings_uses_configured_login_attr_in_ad_filter(self):
        from .settings.helpers import ldap_settings

        env = {
            'AUTH_LDAP_SERVER_URI': 'ldaps://ldap.example.com:636',
            'AUTH_LDAP_BIND_DN': 'cn=svc,dc=example,dc=com',
            'AUTH_LDAP_BIND_PASSWORD': 'secret',
            'AUTH_LDAP_USER_SEARCH_BASE': 'ou=Users,dc=example,dc=com',
            'AUTH_LDAP_LOGIN_ATTR': 'userPrincipalName',
        }

        with patch.dict(os.environ, env, clear=False):
            settings = ldap_settings(mock_ldap=False)

        self.assertEqual(settings['AUTH_LDAP_LOGIN_ATTR'], 'userPrincipalName')
        self.assertEqual(
            settings['AUTH_LDAP_USER_SEARCH_FILTER'],
            '(&(objectClass=user)(!(objectClass=computer))(userPrincipalName=%(user)s))',
        )

    def test_prod_env_example_uses_repo_relative_ldap_ca_path(self):
        prod_example = (
            Path(__file__).resolve().parent.parent / 'env-examples' / 'prod.env.example'
        ).read_text(encoding='utf-8')

        line = next(
            current_line
            for current_line in prod_example.splitlines()
            if current_line.startswith('AUTH_LDAP_CA_CERT_PATH=')
        )
        self.assertEqual(line, 'AUTH_LDAP_CA_CERT_PATH=certs/ldap-ca.crt')


class ReverseProxyHttpsSettingsTest(SimpleTestCase):
    def test_reverse_proxy_https_settings_sets_secure_proxy_defaults(self):
        from .settings.helpers import reverse_proxy_https_settings

        settings = reverse_proxy_https_settings(
            allowed_hosts=['katalog-dwh-test.int.mou.cz', 'localhost']
        )

        self.assertEqual(
            settings['CSRF_TRUSTED_ORIGINS'],
            ['https://katalog-dwh-test.int.mou.cz', 'https://localhost'],
        )
        self.assertEqual(settings['SECURE_PROXY_SSL_HEADER'], ('HTTP_X_FORWARDED_PROTO', 'https'))
        self.assertTrue(settings['CSRF_COOKIE_SECURE'])
        self.assertTrue(settings['SESSION_COOKIE_SECURE'])

    def test_staging_settings_enable_secure_proxy_defaults(self):
        env = {
            'SECRET_KEY': 'test-secret',
            'DEBUG': 'True',
            'ALLOWED_HOSTS': 'katalog-dwh-test.int.mou.cz',
            'SITE_URL': 'https://katalog-dwh-test.int.mou.cz',
            'POSTGRES_DB': 'catalogue',
            'POSTGRES_USER': 'catalogue',
            'POSTGRES_PASSWORD': 'catalogue',
            'POSTGRES_HOST': 'db',
            'POSTGRES_PORT': '5432',
            'AUTH_DB_NAME': 'auth_db',
            'AUTH_DB_USER': 'catalogue',
            'AUTH_DB_PASSWORD': 'catalogue',
            'AUTH_DB_HOST': 'db',
            'AUTH_DB_PORT': '5432',
            'METADATA_DB_NAME': 'metadata_db',
            'METADATA_DB_USER': 'catalogue',
            'METADATA_DB_PASSWORD': 'catalogue',
            'METADATA_DB_HOST': 'db',
            'METADATA_DB_PORT': '5432',
            'FAIR_GENOMES_DB_NAME': 'fair_genomes_db',
            'FAIR_GENOMES_DB_USER': 'catalogue',
            'FAIR_GENOMES_DB_PASSWORD': 'catalogue',
            'FAIR_GENOMES_DB_HOST': 'db',
            'FAIR_GENOMES_DB_PORT': '5432',
            'MOCK_LDAP': 'True',
            'MOCK_FAIR_GENOMES': 'True',
            'MOCK_ALVAO': 'True',
        }

        with patch.dict(os.environ, env, clear=False):
            module = importlib.import_module('catalogue.settings.staging')
            module = importlib.reload(module)

        self.assertEqual(
            module.CSRF_TRUSTED_ORIGINS,
            ['https://katalog-dwh-test.int.mou.cz'],
        )
        self.assertEqual(module.SECURE_PROXY_SSL_HEADER, ('HTTP_X_FORWARDED_PROTO', 'https'))
        self.assertTrue(module.CSRF_COOKIE_SECURE)
        self.assertTrue(module.SESSION_COOKIE_SECURE)


class GrafanaAuthCheckTest(TestCase):
    """Tests for the internal Grafana staff-auth gate."""

    databases = {'default', 'auth_db'}

    def setUp(self):
        self.url = '/internal/auth/grafana/'

    def test_returns_401_for_anonymous_user(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_returns_403_for_authenticated_non_staff_user(self):
        user = User.objects.create_user(username='viewer', password='secret')
        self.client.force_login(user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_returns_200_for_staff_user(self):
        user = User.objects.create_user(username='admin-user', password='secret', is_staff=True)
        self.client.force_login(user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)


class AuthRouterTest(TestCase):
    """Tests for the AuthRouter database router."""

    databases = {'default', 'auth_db'}

    def setUp(self):
        self.router = AuthRouter()

    def test_db_for_read_auth_model(self):
        """Auth models are routed to auth_db for reads."""
        self.assertEqual(self.router.db_for_read(User), 'auth_db')

    def test_db_for_write_auth_model(self):
        """Auth models are routed to auth_db for writes."""
        self.assertEqual(self.router.db_for_write(User), 'auth_db')

    def test_db_for_read_non_auth_model(self):
        """Non-auth models return None (defer to next router)."""
        from ticketing.models import TicketRequest

        self.assertIsNone(self.router.db_for_read(TicketRequest))

    def test_db_for_write_non_auth_model(self):
        """Non-auth models return None."""
        from ticketing.models import TicketRequest

        self.assertIsNone(self.router.db_for_write(TicketRequest))

    def test_allow_migrate_auth_to_auth_db(self):
        """Auth app can migrate to auth_db."""
        self.assertTrue(self.router.allow_migrate('auth_db', 'auth'))

    def test_allow_migrate_auth_to_default(self):
        """Auth app cannot migrate to default."""
        self.assertFalse(self.router.allow_migrate('default', 'auth'))

    def test_allow_migrate_non_auth(self):
        """Non-auth apps return None."""
        self.assertIsNone(self.router.allow_migrate('default', 'ticketing'))

    def test_allow_relation_same_auth_apps(self):
        """Relations between auth apps are allowed."""
        obj1 = User(username='test1')
        obj2 = User(username='test2')
        self.assertTrue(self.router.allow_relation(obj1, obj2))

    def test_allow_relation_auth_and_non_auth(self):
        """Relations between auth and non-auth models are blocked."""
        from ticketing.models import TicketRequest

        user = User(username='test')
        ticket = TicketRequest(requester_email='t@e.com')
        self.assertFalse(self.router.allow_relation(user, ticket))


class WarehouseRouterTest(TestCase):
    """Tests for the WarehouseRouter database router."""

    databases = {'default', 'auth_db'}

    def setUp(self):
        self.router = WarehouseRouter()

    def test_db_for_read_warehouse(self):
        """Warehouse models are routed to metadata_db."""
        from warehouse.models import Dataset

        self.assertEqual(self.router.db_for_read(Dataset), 'metadata_db')

    def test_db_for_read_fair_genomes(self):
        """Fair genomes models are routed to fair_genomes_db."""
        from fair_genomes.models import Dataset

        self.assertEqual(self.router.db_for_read(Dataset), 'fair_genomes_db')

    def test_db_for_read_ticketing(self):
        """Ticketing models are routed to default."""
        from ticketing.models import TicketRequest

        self.assertEqual(self.router.db_for_read(TicketRequest), 'default')

    def test_db_for_write_warehouse(self):
        """Warehouse models write to metadata_db."""
        from warehouse.models import Dataset

        self.assertEqual(self.router.db_for_write(Dataset), 'metadata_db')

    def test_db_for_write_fair_genomes(self):
        """Fair genomes models write to fair_genomes_db."""
        from fair_genomes.models import Dataset

        self.assertEqual(self.router.db_for_write(Dataset), 'fair_genomes_db')

    def test_db_for_write_ticketing(self):
        """Ticketing models write to default."""
        from ticketing.models import TicketRequest

        self.assertEqual(self.router.db_for_write(TicketRequest), 'default')

    def test_allow_migrate_fair_genomes(self):
        """Fair genomes can migrate to fair_genomes_db."""
        self.assertTrue(self.router.allow_migrate('fair_genomes_db', 'fair_genomes'))

    def test_allow_migrate_fair_genomes_wrong_db(self):
        """Fair genomes cannot migrate to default."""
        self.assertFalse(self.router.allow_migrate('default', 'fair_genomes'))

    def test_allow_migrate_warehouse(self):
        """Warehouse models are never migrated by Django."""
        self.assertFalse(self.router.allow_migrate('metadata_db', 'warehouse'))

    def test_allow_migrate_ticketing(self):
        """Ticketing can migrate to default."""
        self.assertTrue(self.router.allow_migrate('default', 'ticketing'))

    def test_allow_relation_same_db(self):
        """Relations within same database are allowed."""
        from ticketing.models import TicketRequest, TicketRequestItem

        t = TicketRequest(requester_email='t@e.com')
        item = TicketRequestItem(ticket_request=t)
        self.assertTrue(self.router.allow_relation(t, item))

    def test_allow_relation_different_db(self):
        """Relations across databases are blocked."""
        from fair_genomes.models import Dataset
        from ticketing.models import TicketRequest

        fg_dataset = Dataset(name='fg-ds1')
        ticket = TicketRequest(requester_email='t@e.com')
        self.assertFalse(self.router.allow_relation(fg_dataset, ticket))


class AttachDistributionsTest(SimpleTestCase):
    def test_attach_distributions_returns_new_dataset_objects(self):
        from shared.catalogue_assemblers import attach_distributions
        from shared.dtos import UnifiedDataset, UnifiedDistribution

        dataset = UnifiedDataset(app='warehouse', name='ds-1', title='Dataset One')
        distributions = [
            UnifiedDistribution(
                app='warehouse',
                name='dist-1',
                dataset_name='ds-1',
                title='Distribution One',
            )
        ]

        attached = attach_distributions([dataset], distributions)

        self.assertEqual(dataset.distributions, [])
        self.assertEqual(len(attached), 1)
        self.assertIsNot(attached[0], dataset)
        self.assertEqual(
            [distribution.name for distribution in attached[0].distributions],
            ['dist-1'],
        )


class SourceLoaderRegistryTest(SimpleTestCase):
    def test_get_export_source_apps_uses_registered_sources(self):
        from shared.source_loaders import get_export_source_apps

        self.assertEqual(get_export_source_apps(), ('warehouse', 'fair_genomes'))

    def test_get_apps_with_table_columns_uses_registered_sources(self):
        from shared.source_loaders import get_apps_with_table_columns

        self.assertEqual(get_apps_with_table_columns(), frozenset({'warehouse'}))

    def test_get_export_models_returns_none_for_unknown_source(self):
        from shared.source_loaders import get_export_models

        self.assertEqual(get_export_models('unknown_source'), (None, None, None))

    def test_get_export_models_resolves_registered_source_models(self):
        from fair_genomes.models import Dataset as FairDataset
        from shared.source_loaders import get_export_models
        from warehouse.models import Dataset as WarehouseDataset

        wh_db_alias, _, wh_dataset_model = get_export_models('warehouse')
        fg_db_alias, _, fg_dataset_model = get_export_models('fair_genomes')

        self.assertEqual(wh_db_alias, 'metadata_db')
        self.assertIs(wh_dataset_model, WarehouseDataset)
        self.assertEqual(fg_db_alias, 'fair_genomes_db')
        self.assertIs(fg_dataset_model, FairDataset)

    def test_export_loaders_return_none_for_unknown_source(self):
        from shared.source_loaders import load_export_catalog, load_export_dataset

        self.assertIsNone(load_export_dataset('unknown_source', 'dataset-1'))
        self.assertIsNone(load_export_catalog('unknown_source', 'catalog-1'))


class CompleteExportCatalogueAssemblerTest(SimpleTestCase):
    @patch(
        'shared.catalogue_assemblers.map_export_catalog',
        return_value=SimpleNamespace(name='catalog-1'),
    )
    @patch(
        'shared.catalogue_assemblers.map_export_dataset',
        return_value=SimpleNamespace(name='dataset-1'),
    )
    def test_build_complete_export_catalogue_skips_failing_source(
        self,
        mock_map_dataset,
        mock_map_catalog,
    ):
        from shared.catalogue_assemblers import build_complete_export_catalogue

        def get_models(app):
            if app == 'warehouse':
                return 'metadata_db', object, object
            return 'fair_genomes_db', object, object

        def get_catalog_queryset(db_alias, _catalog_model):
            if db_alias == 'fair_genomes_db':
                raise RuntimeError('boom')
            return [SimpleNamespace(name='catalog-1')]

        def get_dataset_queryset(app, db_alias, _dataset_model):
            if db_alias == 'fair_genomes_db':
                raise RuntimeError('boom')
            return [SimpleNamespace(name='dataset-1', catalog_id='catalog-1')]

        catalogs, orphan_datasets = build_complete_export_catalogue(
            apps=('warehouse', 'fair_genomes'),
            get_models=get_models,
            get_catalog_queryset=get_catalog_queryset,
            get_dataset_queryset=get_dataset_queryset,
        )

        self.assertEqual([catalog.name for catalog in catalogs], ['catalog-1'])
        self.assertEqual(orphan_datasets, [])
        mock_map_catalog.assert_called_once()
        mock_map_dataset.assert_called_once()
