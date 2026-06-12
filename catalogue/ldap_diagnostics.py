"""LDAP diagnostics shared by the management command and standalone script."""

from __future__ import annotations

import os
import re
import socket
import ssl
from contextlib import suppress
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

START_TLS_OID = '1.3.6.1.4.1.1466.20037'
LOGIN_ATTR_CANDIDATES = ('sAMAccountName', 'userPrincipalName', 'mail')
ROOT_DSE_ATTRS = (
    'defaultNamingContext',
    'namingContexts',
    'supportedExtension',
)
LDAP_ATTR_RE = re.compile(r'^[A-Za-z][A-Za-z0-9.-]*$')


class LdapDiagnosticError(Exception):
    """Raised when the LDAP diagnostic cannot complete."""


@dataclass(frozen=True)
class LdapEndpoint:
    scheme: str
    host: str
    port: int


@dataclass(frozen=True)
class LdapDiagnosticConfig:
    server_uri: str
    bind_dn: str
    bind_password: str
    user_search_base: str = ''
    login_attr: str = 'sAMAccountName'
    start_tls: bool = False
    timeout: int = 10


@dataclass(frozen=True)
class RootDseInfo:
    default_naming_context: str
    naming_contexts: tuple[str, ...]
    supports_start_tls: bool


@dataclass(frozen=True)
class UserSearchCheck:
    base_dn: str
    login_attr: str
    found: bool
    error: str = ''


def import_ldap_module() -> Any:
    try:
        import ldap  # type: ignore[import-not-found]
    except ImportError as exc:
        raise LdapDiagnosticError(
            'python-ldap is not installed in this environment. Run the check inside the web '
            'container or install project requirements first.'
        ) from exc
    return ldap


def parse_bool(value: str | bool | None, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or value == '':
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def load_config_from_env(*, timeout: int, require_search_base: bool) -> LdapDiagnosticConfig:
    server_uri = os.environ.get('AUTH_LDAP_SERVER_URI', '').strip()
    bind_dn = os.environ.get('AUTH_LDAP_BIND_DN', '').strip()
    bind_password = os.environ.get('AUTH_LDAP_BIND_PASSWORD', '')
    user_search_base = os.environ.get('AUTH_LDAP_USER_SEARCH_BASE', '').strip()
    login_attr = os.environ.get('AUTH_LDAP_LOGIN_ATTR', 'sAMAccountName').strip()
    start_tls = parse_bool(os.environ.get('AUTH_LDAP_START_TLS'), default=False)

    missing = [
        key
        for key, value in (
            ('AUTH_LDAP_SERVER_URI', server_uri),
            ('AUTH_LDAP_BIND_DN', bind_dn),
            ('AUTH_LDAP_BIND_PASSWORD', bind_password),
        )
        if not value
    ]
    if require_search_base and not user_search_base:
        missing.append('AUTH_LDAP_USER_SEARCH_BASE')
    if missing:
        raise LdapDiagnosticError(f'Missing required LDAP env values: {", ".join(missing)}')

    return LdapDiagnosticConfig(
        server_uri=server_uri,
        bind_dn=bind_dn,
        bind_password=bind_password,
        user_search_base=user_search_base,
        login_attr=login_attr or 'sAMAccountName',
        start_tls=start_tls,
        timeout=timeout,
    )


def parse_endpoint(server_uri: str) -> LdapEndpoint:
    parsed = urlsplit(server_uri)
    if parsed.scheme not in {'ldap', 'ldaps'} or not parsed.hostname:
        raise LdapDiagnosticError(
            'AUTH_LDAP_SERVER_URI must look like ldap://host:389 or ldaps://host:636.'
        )
    return LdapEndpoint(
        scheme=parsed.scheme,
        host=parsed.hostname,
        port=parsed.port or (636 if parsed.scheme == 'ldaps' else 389),
    )


def configured_ldap_cafile() -> str:
    return (
        os.environ.get('LDAPTLS_CACERT')
        or os.environ.get('SSL_CERT_FILE')
        or os.environ.get('REQUESTS_CA_BUNDLE')
        or ssl.get_default_verify_paths().cafile
        or ''
    )


def validate_transport_config(config: LdapDiagnosticConfig) -> list[str]:
    endpoint = parse_endpoint(config.server_uri)
    warnings: list[str] = []
    if endpoint.scheme == 'ldaps' and config.start_tls:
        raise LdapDiagnosticError(
            'AUTH_LDAP_START_TLS must be False when AUTH_LDAP_SERVER_URI uses ldaps://.'
        )
    if endpoint.scheme == 'ldap' and not config.start_tls:
        warnings.append(
            'AUTH_LDAP_SERVER_URI uses ldap:// and AUTH_LDAP_START_TLS=False; credentials are '
            'sent without LDAP transport encryption unless a network layer protects them.'
        )
    return warnings


def probe_ldaps_tls(config: LdapDiagnosticConfig, *, cafile: str) -> str:
    endpoint = parse_endpoint(config.server_uri)
    if endpoint.scheme != 'ldaps':
        return ''
    if cafile and not os.path.isfile(cafile):
        raise LdapDiagnosticError(f'Configured LDAP CA bundle does not exist: {cafile}')

    context = ssl.create_default_context(cafile=cafile or None)
    try:
        with (
            socket.create_connection(
                (endpoint.host, endpoint.port), timeout=config.timeout
            ) as sock,
            context.wrap_socket(sock, server_hostname=endpoint.host) as tls_sock,
        ):
            return tls_sock.version() or 'unknown'
    except Exception as exc:
        raise LdapDiagnosticError(f'LDAP TLS handshake failed: {exc}') from exc


def _set_ldap_option(ldap_module: Any, target: Any, option_name: str, value: Any) -> None:
    option = getattr(ldap_module, option_name, None)
    if option is not None:
        target.set_option(option, value)


def bind_service_account(config: LdapDiagnosticConfig) -> Any:
    ldap_module = import_ldap_module()
    connection = ldap_module.initialize(config.server_uri)
    _set_ldap_option(ldap_module, connection, 'OPT_PROTOCOL_VERSION', 3)
    _set_ldap_option(ldap_module, connection, 'OPT_REFERRALS', 0)
    _set_ldap_option(ldap_module, connection, 'OPT_NETWORK_TIMEOUT', config.timeout)
    _set_ldap_option(ldap_module, connection, 'OPT_TIMEOUT', config.timeout)

    try:
        if config.start_tls:
            connection.start_tls_s()
        connection.simple_bind_s(config.bind_dn, config.bind_password)
    except Exception as exc:
        close_connection(connection)
        raise LdapDiagnosticError(f'LDAP service account bind failed: {exc}') from exc
    return connection


def close_connection(connection: Any) -> None:
    for method_name in ('unbind_s', 'unbind'):
        method = getattr(connection, method_name, None)
        if method is not None:
            with suppress(Exception):
                method()
            return


def _decode_ldap_value(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return str(value)


def _attr_values(attrs: dict[str, Any], name: str) -> list[str]:
    for key, values in attrs.items():
        if key.lower() == name.lower():
            if isinstance(values, list | tuple):
                return [_decode_ldap_value(value) for value in values]
            return [_decode_ldap_value(values)]
    return []


def read_root_dse(connection: Any) -> RootDseInfo:
    ldap_module = import_ldap_module()
    try:
        result = connection.search_s(
            '',
            ldap_module.SCOPE_BASE,
            '(objectClass=*)',
            list(ROOT_DSE_ATTRS),
        )
    except Exception as exc:
        raise LdapDiagnosticError(f'LDAP RootDSE query failed: {exc}') from exc

    attrs = result[0][1] if result else {}
    default_contexts = _attr_values(attrs, 'defaultNamingContext')
    naming_contexts = tuple(_attr_values(attrs, 'namingContexts'))
    supported_extensions = set(_attr_values(attrs, 'supportedExtension'))
    return RootDseInfo(
        default_naming_context=default_contexts[0] if default_contexts else '',
        naming_contexts=naming_contexts,
        supports_start_tls=START_TLS_OID in supported_extensions,
    )


def user_presence_filter(login_attr: str) -> str:
    if not LDAP_ATTR_RE.fullmatch(login_attr):
        raise LdapDiagnosticError(f'Invalid LDAP login attribute name: {login_attr}')
    return f'(&(objectClass=user)(!(objectClass=computer))({login_attr}=*))'


def check_user_search(
    connection: Any,
    *,
    base_dn: str,
    login_attr: str,
    timeout: int,
) -> UserSearchCheck:
    ldap_module = import_ldap_module()
    if not base_dn:
        return UserSearchCheck(
            base_dn=base_dn, login_attr=login_attr, found=False, error='empty base'
        )

    try:
        result = connection.search_ext_s(
            base_dn,
            ldap_module.SCOPE_SUBTREE,
            user_presence_filter(login_attr),
            [login_attr, 'mail', 'displayName'],
            timeout=timeout,
            sizelimit=1,
        )
    except Exception as exc:
        size_limit_error = getattr(ldap_module, 'SIZELIMIT_EXCEEDED', None)
        if size_limit_error is not None and isinstance(exc, size_limit_error):
            return UserSearchCheck(base_dn=base_dn, login_attr=login_attr, found=True)
        return UserSearchCheck(base_dn=base_dn, login_attr=login_attr, found=False, error=str(exc))

    return UserSearchCheck(base_dn=base_dn, login_attr=login_attr, found=bool(result))


def candidate_search_bases(
    *,
    configured_base: str,
    root_dse: RootDseInfo,
) -> tuple[str, ...]:
    candidates: list[str] = []
    for value in (
        configured_base,
        root_dse.default_naming_context,
        *root_dse.naming_contexts,
    ):
        if value and value not in candidates:
            candidates.append(value)
    return tuple(candidates)


def discover_user_searches(
    connection: Any,
    *,
    bases: tuple[str, ...],
    timeout: int,
) -> list[UserSearchCheck]:
    checks: list[UserSearchCheck] = []
    for base_dn in bases:
        for login_attr in LOGIN_ATTR_CANDIDATES:
            checks.append(
                check_user_search(
                    connection,
                    base_dn=base_dn,
                    login_attr=login_attr,
                    timeout=timeout,
                )
            )
    return checks
