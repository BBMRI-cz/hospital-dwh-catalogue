#!/usr/bin/env python
"""Discover LDAP env candidates using the existing service-account env values.

This script does not import Django settings, so it can run before
AUTH_LDAP_USER_SEARCH_BASE is known. It reads AUTH_LDAP_* values from the
environment and never prints the service account password.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from catalogue.ldap_diagnostics import (  # noqa: E402
    LOGIN_ATTR_CANDIDATES,
    LdapDiagnosticError,
    bind_service_account,
    candidate_search_bases,
    close_connection,
    configured_ldap_cafile,
    discover_user_searches,
    load_config_from_env,
    parse_endpoints,
    probe_ldaps_tls,
    read_root_dse,
    validate_transport_config,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Discover LDAP search-base and login-attribute candidates from env.'
    )
    parser.add_argument('--timeout', type=int, default=10)
    args = parser.parse_args()

    try:
        config = load_config_from_env(timeout=args.timeout, require_search_base=False)
        endpoints = parse_endpoints(config.server_uri)
        cafile = configured_ldap_cafile()

        print(
            'LDAP endpoints: '
            + ', '.join(
                f'{endpoint.scheme}://{endpoint.host}:{endpoint.port}' for endpoint in endpoints
            )
        )
        print(f'LDAP StartTLS: {config.start_tls}')
        print(f'LDAP CA bundle: {cafile or "<system default>"}')
        print('LDAP bind account: <current AUTH_LDAP_BIND_DN value>')

        for warning in validate_transport_config(config):
            print(f'WARNING: {warning}')

        tls_protocol = probe_ldaps_tls(config, cafile=cafile)
        if tls_protocol:
            print(f'LDAP TLS protocol: {tls_protocol}')

        connection = bind_service_account(config)
        try:
            print('LDAP service account bind: OK')
            root_dse = read_root_dse(connection)
            print(f'Default naming context: {root_dse.default_naming_context or "<empty>"}')
            print(f'Naming contexts: {", ".join(root_dse.naming_contexts) or "<empty>"}')
            print(f'Server supports StartTLS: {root_dse.supports_start_tls}')

            bases = candidate_search_bases(
                configured_base=config.user_search_base,
                root_dse=root_dse,
            )
            print(f'Candidate search bases: {", ".join(bases) or "<empty>"}')
            print(f'Candidate login attributes: {", ".join(LOGIN_ATTR_CANDIDATES)}')

            checks = discover_user_searches(connection, bases=bases, timeout=args.timeout)
            for check in checks:
                status = 'OK' if check.found else 'no match'
                detail = f' ({check.error})' if check.error else ''
                print(f'- {check.base_dn} with {check.login_attr}: {status}{detail}')

            recommendation = next((check for check in checks if check.found), None)
            if recommendation is None:
                raise LdapDiagnosticError(
                    'No candidate search base/login attribute returned a user entry.'
                )

            print('')
            print('Recommended LDAP env values to verify:')
            print(f'AUTH_LDAP_SERVER_URI={config.server_uri}')
            print('AUTH_LDAP_BIND_DN=<current service account value>')
            print('AUTH_LDAP_BIND_PASSWORD=<current secret value>')
            print(f'AUTH_LDAP_USER_SEARCH_BASE={recommendation.base_dn}')
            print(f'AUTH_LDAP_LOGIN_ATTR={recommendation.login_attr}')
            print(f'AUTH_LDAP_START_TLS={"True" if config.start_tls else "False"}')
        finally:
            close_connection(connection)
    except LdapDiagnosticError as exc:
        print(f'LDAP discovery failed: {exc}', file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
