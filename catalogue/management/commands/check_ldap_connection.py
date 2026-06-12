"""Check LDAP TLS, service-account bind, and user-search configuration."""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from catalogue.ldap_diagnostics import (
    LOGIN_ATTR_CANDIDATES,
    LdapDiagnosticConfig,
    LdapDiagnosticError,
    bind_service_account,
    candidate_search_bases,
    check_user_search,
    close_connection,
    configured_ldap_cafile,
    discover_user_searches,
    parse_endpoint,
    probe_ldaps_tls,
    read_root_dse,
    validate_transport_config,
)


class Command(BaseCommand):
    help = 'Check LDAP TLS trust, service account bind, and configured user search.'

    def add_arguments(self, parser):
        parser.add_argument('--timeout', type=int, default=10)
        parser.add_argument(
            '--discover',
            action='store_true',
            help='Also probe RootDSE naming contexts and common login attributes.',
        )

    def handle(self, *args, **options):
        timeout = int(options['timeout'])
        discover = bool(options['discover'])
        if getattr(settings, 'MOCK_LDAP', False):
            self.stdout.write('MOCK_LDAP=True; skipping LDAP check.')
            return

        try:
            config = self._config_from_settings(timeout=timeout)
            warnings = validate_transport_config(config)
            endpoint = parse_endpoint(config.server_uri)
            cafile = configured_ldap_cafile()

            self.stdout.write(f'LDAP host: {endpoint.host}:{endpoint.port}')
            self.stdout.write(f'LDAP transport: {endpoint.scheme}; StartTLS: {config.start_tls}')
            self.stdout.write(f'LDAP CA bundle: {cafile or "<system default>"}')
            self.stdout.write(f'Configured user search base: {config.user_search_base}')
            self.stdout.write(f'Configured login attribute: {config.login_attr}')

            for warning in warnings:
                self.stdout.write(self.style.WARNING(f'WARNING: {warning}'))

            tls_protocol = probe_ldaps_tls(config, cafile=cafile)
            if tls_protocol:
                self.stdout.write(f'LDAP TLS protocol: {tls_protocol}')

            connection = bind_service_account(config)
            try:
                self.stdout.write('LDAP service account bind: OK')
                root_dse = read_root_dse(connection)
                self.stdout.write(
                    f'LDAP default naming context: {root_dse.default_naming_context or "<empty>"}'
                )
                self.stdout.write(
                    f'LDAP naming contexts: {", ".join(root_dse.naming_contexts) or "<empty>"}'
                )
                self.stdout.write(f'LDAP server supports StartTLS: {root_dse.supports_start_tls}')

                configured_search = check_user_search(
                    connection,
                    base_dn=config.user_search_base,
                    login_attr=config.login_attr,
                    timeout=timeout,
                )
                if not configured_search.found:
                    message = (
                        'Configured LDAP user search did not find a user entry for '
                        f'{config.login_attr}=* below {config.user_search_base}.'
                    )
                    if configured_search.error:
                        message = f'{message} LDAP error: {configured_search.error}'
                    raise CommandError(message)
                self.stdout.write('Configured LDAP user search: OK')

                if discover:
                    self._print_discovery(connection, config, root_dse, timeout=timeout)
            finally:
                close_connection(connection)
        except LdapDiagnosticError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS('LDAP connection check passed.'))

    def _config_from_settings(self, *, timeout: int) -> LdapDiagnosticConfig:
        server_uri = str(getattr(settings, 'AUTH_LDAP_SERVER_URI', '') or '').strip()
        bind_dn = str(getattr(settings, 'AUTH_LDAP_BIND_DN', '') or '').strip()
        bind_password = str(getattr(settings, 'AUTH_LDAP_BIND_PASSWORD', '') or '')
        user_search_base = str(getattr(settings, 'AUTH_LDAP_USER_SEARCH_BASE', '') or '').strip()
        login_attr = str(getattr(settings, 'AUTH_LDAP_LOGIN_ATTR', 'sAMAccountName') or '').strip()
        missing = [
            key
            for key, value in (
                ('AUTH_LDAP_SERVER_URI', server_uri),
                ('AUTH_LDAP_BIND_DN', bind_dn),
                ('AUTH_LDAP_BIND_PASSWORD', bind_password),
                ('AUTH_LDAP_USER_SEARCH_BASE', user_search_base),
            )
            if not value
        ]
        if missing:
            raise LdapDiagnosticError(f'Missing required LDAP settings: {", ".join(missing)}')

        return LdapDiagnosticConfig(
            server_uri=server_uri,
            bind_dn=bind_dn,
            bind_password=bind_password,
            user_search_base=user_search_base,
            login_attr=login_attr or 'sAMAccountName',
            start_tls=bool(getattr(settings, 'AUTH_LDAP_START_TLS', False)),
            timeout=timeout,
        )

    def _print_discovery(self, connection, config, root_dse, *, timeout: int) -> None:
        self.stdout.write('')
        self.stdout.write('LDAP discovery:')
        bases = candidate_search_bases(
            configured_base=config.user_search_base,
            root_dse=root_dse,
        )
        self.stdout.write(f'Candidate search bases: {", ".join(bases) or "<empty>"}')
        self.stdout.write(f'Candidate login attributes: {", ".join(LOGIN_ATTR_CANDIDATES)}')

        checks = discover_user_searches(connection, bases=bases, timeout=timeout)
        for check in checks:
            status = 'OK' if check.found else 'no match'
            detail = f' ({check.error})' if check.error else ''
            self.stdout.write(f'- {check.base_dn} with {check.login_attr}: {status}{detail}')

        recommendation = next((check for check in checks if check.found), None)
        if recommendation is None:
            self.stdout.write(
                self.style.WARNING(
                    'No candidate search base/login attribute returned a user entry.'
                )
            )
            return

        self.stdout.write('')
        self.stdout.write('Recommended LDAP env values to verify:')
        self.stdout.write(f'AUTH_LDAP_SERVER_URI={config.server_uri}')
        self.stdout.write('AUTH_LDAP_BIND_DN=<current service account value>')
        self.stdout.write('AUTH_LDAP_BIND_PASSWORD=<current secret value>')
        self.stdout.write(f'AUTH_LDAP_USER_SEARCH_BASE={recommendation.base_dn}')
        self.stdout.write(f'AUTH_LDAP_LOGIN_ATTR={recommendation.login_attr}')
        self.stdout.write(f'AUTH_LDAP_START_TLS={"True" if config.start_tls else "False"}')
