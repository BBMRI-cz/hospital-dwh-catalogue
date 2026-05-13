"""
Tests for the catalogue project configuration.

Covers URL routing, views, and database routers.
"""

import importlib
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from fair_genomes.models import Dataset as FairDataset
from shared.catalogue_assemblers import attach_distributions, build_complete_export_catalogue
from shared.dtos import UnifiedDataset, UnifiedDistribution
from shared.source_loaders import (
    get_apps_with_table_columns,
    get_source_adapter,
    get_source_apps,
    load_export_catalog,
    load_export_dataset,
)
from ticketing.models import TicketRequest, TicketRequestItem
from warehouse.models import Dataset as WarehouseDataset

from .routers import AuthRouter, WarehouseRouter
from .settings.helpers import (
    alvao_settings,
    ldap_settings,
    positive_int_or_default,
    reverse_proxy_https_settings,
)


class _FakeLDAPSearch:
    def __init__(self, base_dn, scope, filterstr):
        self.base_dn = base_dn
        self.scope = scope
        self.filterstr = filterstr


def _ldap_test_modules():
    fake_ldap = SimpleNamespace(
        SCOPE_SUBTREE=1,
        OPT_REFERRALS=2,
        OPT_NETWORK_TIMEOUT=3,
    )
    fake_ldap_config = SimpleNamespace(LDAPSearch=_FakeLDAPSearch)
    return {
        'ldap': fake_ldap,
        'django_auth_ldap': SimpleNamespace(config=fake_ldap_config),
        'django_auth_ldap.config': fake_ldap_config,
    }


class LdapSettingsTest(SimpleTestCase):
    def test_ldap_settings_default_login_attr_is_samaccountname(self):
        env = {
            'AUTH_LDAP_SERVER_URI': 'ldaps://ldap.example.com:636',
            'AUTH_LDAP_BIND_DN': 'cn=svc,dc=example,dc=com',
            'AUTH_LDAP_BIND_PASSWORD': 'secret',
            'AUTH_LDAP_USER_SEARCH_BASE': 'ou=Users,dc=example,dc=com',
        }

        with (
            patch.dict(os.environ, env, clear=False),
            patch.dict(sys.modules, _ldap_test_modules()),
        ):
            settings = ldap_settings(mock_ldap=False)

        self.assertEqual(settings['AUTH_LDAP_LOGIN_ATTR'], 'sAMAccountName')
        self.assertEqual(
            settings['AUTH_LDAP_USER_SEARCH_FILTER'],
            '(&(objectClass=user)(!(objectClass=computer))(sAMAccountName=%(user)s))',
        )

    def test_ldap_settings_uses_configured_login_attr_in_ad_filter(self):
        env = {
            'AUTH_LDAP_SERVER_URI': 'ldaps://ldap.example.com:636',
            'AUTH_LDAP_BIND_DN': 'cn=svc,dc=example,dc=com',
            'AUTH_LDAP_BIND_PASSWORD': 'secret',
            'AUTH_LDAP_USER_SEARCH_BASE': 'ou=Users,dc=example,dc=com',
            'AUTH_LDAP_LOGIN_ATTR': 'userPrincipalName',
        }

        with (
            patch.dict(os.environ, env, clear=False),
            patch.dict(sys.modules, _ldap_test_modules()),
        ):
            settings = ldap_settings(mock_ldap=False)

        self.assertEqual(settings['AUTH_LDAP_LOGIN_ATTR'], 'userPrincipalName')
        self.assertEqual(
            settings['AUTH_LDAP_USER_SEARCH_FILTER'],
            '(&(objectClass=user)(!(objectClass=computer))(userPrincipalName=%(user)s))',
        )

    def test_prod_env_example_uses_shared_mou_root_ca_for_ldap(self):
        prod_example = (
            Path(__file__).resolve().parent.parent / 'env-examples' / 'prod.env.example'
        ).read_text(encoding='utf-8')

        self.assertNotIn('AUTH_LDAP_CA_CERT_PATH=', prod_example)
        self.assertIn('MOU_ROOT_CA_CERT_PATH=certs/MOURootCA.crt', prod_example)

    def test_staging_and_prod_compose_use_shared_ca_bundle_for_python_tls(self):
        repo_root = Path(__file__).resolve().parent.parent

        for compose_file in ('staging.yml', 'prod.yml'):
            with self.subTest(compose_file=compose_file):
                compose = (repo_root / 'docker' / 'compose' / compose_file).read_text(
                    encoding='utf-8'
                )

                self.assertIn('REQUESTS_CA_BUNDLE: /tmp/mou-ca-bundle.crt', compose)
                self.assertIn('SSL_CERT_FILE: /tmp/mou-ca-bundle.crt', compose)


class SettingsHelpersTest(SimpleTestCase):
    def test_alvao_settings_reads_default_service_id(self):
        env = {
            'ALVAO_API_URL': 'https://alvao.example/AlvaoRestApi/v1',
            'ALVAO_SERVICE_ACCOUNT_USERNAME': 'svc',
            'ALVAO_SERVICE_ACCOUNT_PASSWORD': 'secret',
            'ALVAO_TEST_REQUESTER_EMAIL': 'alvao-user@example.com',
            'ALVAO_DEFAULT_SERVICE_ID': '109',
        }

        with patch.dict(os.environ, env, clear=False):
            settings = alvao_settings(mock_alvao=False)

        self.assertEqual(settings['ALVAO_DEFAULT_SERVICE_ID'], 109)
        self.assertEqual(settings['ALVAO_TEST_REQUESTER_EMAIL'], 'alvao-user@example.com')

    def test_positive_int_or_default_returns_positive_values(self):
        self.assertEqual(positive_int_or_default('25', default=15), 25)

    def test_positive_int_or_default_falls_back_to_default_for_invalid_values(self):
        for value in ('0', '-3', 'abc', ''):
            with self.subTest(value=value):
                self.assertEqual(positive_int_or_default(value, default=15), 15)


class CheckRunnerScriptTest(SimpleTestCase):
    def _write_fake_python(self, path: Path, *, imports_ok: bool) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        import_result = 0 if imports_ok else 1
        path.write_text(
            f"""#!/bin/sh
if [ "$1" = "-V" ]; then
    echo "Python 3.12.0"
    exit 0
fi
if [ "$1" = "-c" ]; then
    case "$2" in
        "import django"|"import ruff"|"import mypy"|"import bandit")
            exit {import_result}
            ;;
    esac
fi
exit 1
""",
            encoding='utf-8',
        )
        path.chmod(0o755)

    def test_check_python_prefers_usable_venv_when_dotvenv_is_incomplete(self):
        script_path = Path(__file__).resolve().parent.parent / 'scripts' / 'lib' / 'common.sh'
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            self._write_fake_python(repo_root / '.venv' / 'bin' / 'python', imports_ok=False)
            self._write_fake_python(repo_root / 'venv' / 'bin' / 'python', imports_ok=True)

            command = (
                f'source {shlex.quote(str(script_path))}; '
                f'REPO_ROOT={shlex.quote(str(repo_root))}; '
                'resolve_check_python'
            )
            result = subprocess.run(
                ['bash', '-lc', command],
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.stdout.strip(), str(repo_root / 'venv' / 'bin' / 'python'))


class DeployScriptResetOptionsTest(SimpleTestCase):
    def _deploy_script(self):
        return (Path(__file__).resolve().parent.parent / 'deploy.sh').read_text(encoding='utf-8')

    def test_deploy_script_exposes_volume_reset_modes(self):
        deploy_script = self._deploy_script()

        self.assertIn('--reset-volumes', deploy_script)
        self.assertIn('--reset-volumes-keep-users', deploy_script)
        self.assertIn('down --volumes --remove-orphans', deploy_script)
        self.assertIn('pg_dump', deploy_script)
        self.assertIn('pg_restore', deploy_script)

    def test_deploy_script_runs_post_deploy_diagnostics(self):
        deploy_script = self._deploy_script()

        self.assertIn('python manage.py check_alvao_tls', deploy_script)
        self.assertIn('python manage.py check_observability', deploy_script)
        self.assertIn('WARNING: ALVAO post-deploy check failed.', deploy_script)
        self.assertIn('WARNING: observability post-deploy check failed.', deploy_script)


class ManagementCommandAvailabilityTest(SimpleTestCase):
    def test_runtime_diagnostic_commands_exist(self):
        repo_root = Path(__file__).resolve().parent.parent
        commands = [
            repo_root / 'ticketing' / 'management' / 'commands' / 'check_alvao_tls.py',
            repo_root / 'frontend' / 'management' / 'commands' / 'check_observability.py',
        ]

        for command in commands:
            with self.subTest(command=command.name):
                self.assertTrue(command.is_file())


class ObservabilityConfigTest(SimpleTestCase):
    def test_grafana_dashboards_are_mounted_at_provider_path(self):
        repo_root = Path(__file__).resolve().parent.parent
        compose = (repo_root / 'docker' / 'compose' / 'observability.yml').read_text(
            encoding='utf-8'
        )
        provider = (
            repo_root / 'docker' / 'grafana' / 'provisioning' / 'dashboards' / 'provider.yaml'
        ).read_text(encoding='utf-8')

        self.assertIn('/var/lib/grafana/dashboards:ro', compose)
        self.assertIn('path: /var/lib/grafana/dashboards', provider)

    def test_alloy_waits_for_web_logs_before_starting(self):
        compose = (
            Path(__file__).resolve().parent.parent / 'docker' / 'compose' / 'observability.yml'
        ).read_text(encoding='utf-8')

        self.assertIn('web:', compose)
        self.assertIn('condition: service_healthy', compose)


class ReverseProxyHttpsSettingsTest(SimpleTestCase):
    def test_reverse_proxy_https_settings_sets_secure_proxy_defaults(self):
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
        user = User.objects.create_user(username='staff-user', password='secret', is_staff=True)
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
        self.assertIsNone(self.router.db_for_read(TicketRequest))

    def test_db_for_write_non_auth_model(self):
        """Non-auth models return None."""
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
        self.assertEqual(self.router.db_for_read(WarehouseDataset), 'metadata_db')

    def test_db_for_read_fair_genomes(self):
        """Fair genomes models are routed to fair_genomes_db."""
        self.assertEqual(self.router.db_for_read(FairDataset), 'fair_genomes_db')

    def test_db_for_read_ticketing(self):
        """Ticketing models are routed to default."""
        self.assertEqual(self.router.db_for_read(TicketRequest), 'default')

    def test_db_for_write_warehouse(self):
        """Warehouse models write to metadata_db."""
        self.assertEqual(self.router.db_for_write(WarehouseDataset), 'metadata_db')

    def test_db_for_write_fair_genomes(self):
        """Fair genomes models write to fair_genomes_db."""
        self.assertEqual(self.router.db_for_write(FairDataset), 'fair_genomes_db')

    def test_db_for_write_ticketing(self):
        """Ticketing models write to default."""
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
        t = TicketRequest(requester_email='t@e.com')
        item = TicketRequestItem(ticket_request=t)
        self.assertTrue(self.router.allow_relation(t, item))

    def test_allow_relation_different_db(self):
        """Relations across databases are blocked."""
        fg_dataset = FairDataset(name='fg-ds1')
        ticket = TicketRequest(requester_email='t@e.com')
        self.assertFalse(self.router.allow_relation(fg_dataset, ticket))


class AttachDistributionsTest(SimpleTestCase):
    def test_attach_distributions_returns_new_dataset_objects(self):
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
    def test_get_source_apps_uses_registered_sources(self):
        self.assertEqual(get_source_apps(), ('warehouse', 'fair_genomes'))

    def test_get_apps_with_table_columns_uses_registered_sources(self):
        self.assertEqual(get_apps_with_table_columns(), frozenset({'warehouse'}))

    def test_get_source_adapter_returns_none_for_unknown_source(self):
        self.assertIsNone(get_source_adapter('unknown_source'))

    def test_get_source_adapter_resolves_registered_source_models(self):
        wh_adapter = get_source_adapter('warehouse')
        fg_adapter = get_source_adapter('fair_genomes')

        self.assertIsNotNone(wh_adapter)
        self.assertIsNotNone(fg_adapter)
        assert wh_adapter is not None
        assert fg_adapter is not None
        self.assertEqual(wh_adapter.db_alias, 'metadata_db')
        self.assertIs(wh_adapter.dataset_model, WarehouseDataset)
        self.assertEqual(fg_adapter.db_alias, 'fair_genomes_db')
        self.assertIs(fg_adapter.dataset_model, FairDataset)

    def test_export_loaders_return_none_for_unknown_source(self):
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
        class Source:
            def __init__(self, app):
                self.app = app

            def export_catalog_queryset(self):
                if self.app == 'fair_genomes':
                    raise RuntimeError('boom')
                return [SimpleNamespace(name='catalog-1')]

            def export_dataset_queryset(self):
                if self.app == 'fair_genomes':
                    raise RuntimeError('boom')
                return [SimpleNamespace(name='dataset-1', catalog_id='catalog-1')]

        catalogs, orphan_datasets = build_complete_export_catalogue(
            [Source('warehouse'), Source('fair_genomes')]
        )

        self.assertEqual([catalog.name for catalog in catalogs], ['catalog-1'])
        self.assertEqual(orphan_datasets, [])
        mock_map_catalog.assert_called_once()
        mock_map_dataset.assert_called_once()
