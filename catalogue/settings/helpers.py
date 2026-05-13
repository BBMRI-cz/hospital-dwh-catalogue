"""Reusable settings helpers shared by runtime environment modules."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from decouple import config


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(',') if item.strip()]


def positive_int_or_default(value: str, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def env_list(name: str, *, default: str | None = None) -> list[str]:
    if default is None:
        return config(name, cast=_split_csv)
    return config(name, default=default, cast=_split_csv)


def postgres_db(
    name_var: str,
    user_var: str,
    password_var: str,
    host_var: str,
    port_var: str,
    *,
    name_default: str | None = None,
    user_default: str | None = None,
    password_default: str | None = None,
    host_default: str | None = None,
    port_default: str = '5432',
) -> dict[str, Any]:
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config(name_var, default=name_default)
        if name_default is not None
        else config(name_var),
        'USER': config(user_var, default=user_default)
        if user_default is not None
        else config(user_var),
        'PASSWORD': (
            config(password_var, default=password_default)
            if password_default is not None
            else config(password_var)
        ),
        'HOST': config(host_var, default=host_default)
        if host_default is not None
        else config(host_var),
        'PORT': config(port_var, default=port_default),
        'OPTIONS': {'connect_timeout': 30},
    }


def ldap_settings(*, mock_ldap: bool) -> dict[str, Any]:
    if mock_ldap:
        return {
            'AUTHENTICATION_BACKENDS': [
                'catalogue.mock_ldap.MockLDAPBackend',
                'django.contrib.auth.backends.ModelBackend',
            ]
        }

    import ldap
    from django_auth_ldap.config import LDAPSearch

    ldap_attributes = vars(ldap)
    ldap_scope_subtree = ldap_attributes['SCOPE_SUBTREE']
    ldap_opt_referrals = ldap_attributes['OPT_REFERRALS']
    ldap_opt_network_timeout = ldap_attributes['OPT_NETWORK_TIMEOUT']

    auth_ldap_user_search_base = config('AUTH_LDAP_USER_SEARCH_BASE')
    auth_ldap_login_attr = config('AUTH_LDAP_LOGIN_ATTR', default='sAMAccountName')
    auth_ldap_user_search_filter = (
        f'(&(objectClass=user)(!(objectClass=computer))({auth_ldap_login_attr}=%(user)s))'
    )
    return {
        'AUTHENTICATION_BACKENDS': [
            'django_auth_ldap.backend.LDAPBackend',
            'django.contrib.auth.backends.ModelBackend',
        ],
        'AUTH_LDAP_SERVER_URI': config('AUTH_LDAP_SERVER_URI'),
        'AUTH_LDAP_BIND_DN': config('AUTH_LDAP_BIND_DN'),
        'AUTH_LDAP_BIND_PASSWORD': config('AUTH_LDAP_BIND_PASSWORD'),
        'AUTH_LDAP_USER_SEARCH_BASE': auth_ldap_user_search_base,
        'AUTH_LDAP_LOGIN_ATTR': auth_ldap_login_attr,
        'AUTH_LDAP_USER_SEARCH_FILTER': auth_ldap_user_search_filter,
        'AUTH_LDAP_USER_SEARCH': LDAPSearch(
            auth_ldap_user_search_base,
            ldap_scope_subtree,
            auth_ldap_user_search_filter,
        ),
        'AUTH_LDAP_USER_ATTR_MAP': {
            'first_name': 'givenName',
            'last_name': 'sn',
            'email': 'mail',
        },
        'AUTH_LDAP_ALWAYS_UPDATE_USER': True,
        'AUTH_LDAP_CONNECTION_OPTIONS': {
            ldap_opt_referrals: 0,
            ldap_opt_network_timeout: 30,
        },
        'AUTH_LDAP_START_TLS': config('AUTH_LDAP_START_TLS', default=False, cast=bool),
    }


def fair_genomes_settings(*, mock_fair_genomes: bool) -> dict[str, Any]:
    if mock_fair_genomes:
        return {
            'FAIR_GENOMES_RDF_URL': config('FAIR_GENOMES_RDF_URL', default=''),
            'FAIR_GENOMES_API_URL': config('FAIR_GENOMES_API_URL', default=''),
            'FAIR_GENOMES_API_TOKEN': config('FAIR_GENOMES_API_TOKEN', default=''),
            'FAIR_GENOMES_SYNC_INTERVAL_HOURS': config(
                'FAIR_GENOMES_SYNC_INTERVAL_HOURS', default=24, cast=int
            ),
        }

    return {
        'FAIR_GENOMES_RDF_URL': config('FAIR_GENOMES_RDF_URL'),
        'FAIR_GENOMES_API_URL': config('FAIR_GENOMES_API_URL'),
        'FAIR_GENOMES_API_TOKEN': config('FAIR_GENOMES_API_TOKEN'),
        'FAIR_GENOMES_SYNC_INTERVAL_HOURS': config(
            'FAIR_GENOMES_SYNC_INTERVAL_HOURS', default=24, cast=int
        ),
    }


def alvao_settings(*, mock_alvao: bool) -> dict[str, Any]:
    if mock_alvao:
        return {
            'ALVAO_API_URL': config('ALVAO_API_URL', default=''),
            'ALVAO_SERVICE_ACCOUNT_USERNAME': config('ALVAO_SERVICE_ACCOUNT_USERNAME', default=''),
            'ALVAO_SERVICE_ACCOUNT_PASSWORD': config('ALVAO_SERVICE_ACCOUNT_PASSWORD', default=''),
            'ALVAO_TEST_REQUESTER_EMAIL': config('ALVAO_TEST_REQUESTER_EMAIL', default=''),
            'ALVAO_DEFAULT_SERVICE_ID': config(
                'ALVAO_DEFAULT_SERVICE_ID',
                default=None,
                cast=lambda value: int(value) if value else None,
            ),
        }

    return {
        'ALVAO_API_URL': config('ALVAO_API_URL'),
        'ALVAO_SERVICE_ACCOUNT_USERNAME': config('ALVAO_SERVICE_ACCOUNT_USERNAME'),
        'ALVAO_SERVICE_ACCOUNT_PASSWORD': config('ALVAO_SERVICE_ACCOUNT_PASSWORD'),
        'ALVAO_TEST_REQUESTER_EMAIL': config('ALVAO_TEST_REQUESTER_EMAIL', default=''),
        'ALVAO_DEFAULT_SERVICE_ID': config('ALVAO_DEFAULT_SERVICE_ID', cast=int),
    }


def cache_settings(
    *,
    key_prefix: str,
    redis_default: str = '',
    max_connections: int | None = None,
) -> dict[str, Any]:
    redis_url = config('REDIS_URL', default=redis_default)
    if redis_url:
        options: dict[str, Any] = {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'IGNORE_EXCEPTIONS': True,
        }
        if max_connections is not None:
            options['CONNECTION_POOL_KWARGS'] = {'max_connections': max_connections}
        return {
            'CACHES': {
                'default': {
                    'BACKEND': 'django_redis.cache.RedisCache',
                    'LOCATION': redis_url,
                    'KEY_PREFIX': key_prefix,
                    'OPTIONS': options,
                }
            },
            'SESSION_ENGINE': 'django.contrib.sessions.backends.cache',
            'SESSION_CACHE_ALIAS': 'default',
        }

    return {
        'CACHES': {
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            }
        }
    }


def build_postgres_databases(
    *,
    defaults: dict[str, dict[str, str | None]] | None = None,
) -> dict[str, dict[str, Any]]:
    defaults = defaults or {}
    return {
        'default': postgres_db(
            'POSTGRES_DB',
            'POSTGRES_USER',
            'POSTGRES_PASSWORD',
            'POSTGRES_HOST',
            'POSTGRES_PORT',
            name_default=defaults.get('default', {}).get('name_default'),
            user_default=defaults.get('default', {}).get('user_default'),
            password_default=defaults.get('default', {}).get('password_default'),
            host_default=defaults.get('default', {}).get('host_default'),
        ),
        'auth_db': postgres_db(
            'AUTH_DB_NAME',
            'AUTH_DB_USER',
            'AUTH_DB_PASSWORD',
            'AUTH_DB_HOST',
            'AUTH_DB_PORT',
            name_default=defaults.get('auth_db', {}).get('name_default'),
            user_default=defaults.get('auth_db', {}).get('user_default'),
            password_default=defaults.get('auth_db', {}).get('password_default'),
            host_default=defaults.get('auth_db', {}).get('host_default'),
        ),
        'metadata_db': postgres_db(
            'METADATA_DB_NAME',
            'METADATA_DB_USER',
            'METADATA_DB_PASSWORD',
            'METADATA_DB_HOST',
            'METADATA_DB_PORT',
            name_default=defaults.get('metadata_db', {}).get('name_default'),
            user_default=defaults.get('metadata_db', {}).get('user_default'),
            password_default=defaults.get('metadata_db', {}).get('password_default'),
            host_default=defaults.get('metadata_db', {}).get('host_default'),
        ),
        'fair_genomes_db': postgres_db(
            'FAIR_GENOMES_DB_NAME',
            'FAIR_GENOMES_DB_USER',
            'FAIR_GENOMES_DB_PASSWORD',
            'FAIR_GENOMES_DB_HOST',
            'FAIR_GENOMES_DB_PORT',
            name_default=defaults.get('fair_genomes_db', {}).get('name_default'),
            user_default=defaults.get('fair_genomes_db', {}).get('user_default'),
            password_default=defaults.get('fair_genomes_db', {}).get('password_default'),
            host_default=defaults.get('fair_genomes_db', {}).get('host_default'),
        ),
    }


def build_sqlite_databases(base_dir: Path) -> dict[str, dict[str, Any]]:
    return {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': base_dir / 'test_db.sqlite3',
        },
        'auth_db': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': base_dir / 'test_auth_db.sqlite3',
        },
        'metadata_db': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': base_dir / 'test_metadata_db.sqlite3',
        },
        'fair_genomes_db': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': base_dir / 'test_fair_genomes_db.sqlite3',
        },
    }


def manifest_staticfiles_storage() -> dict[str, dict[str, str]]:
    return {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'},
    }


def console_email_settings() -> dict[str, Any]:
    return {'EMAIL_BACKEND': 'django.core.mail.backends.console.EmailBackend'}


def smtp_email_settings() -> dict[str, Any]:
    return {
        'EMAIL_BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
        'EMAIL_HOST': config('EMAIL_HOST', default='smtp.gmail.com'),
        'EMAIL_PORT': config('EMAIL_PORT', default=587, cast=int),
        'EMAIL_USE_TLS': config('EMAIL_USE_TLS', default=True, cast=bool),
        'EMAIL_HOST_USER': config('EMAIL_HOST_USER', default=''),
        'EMAIL_HOST_PASSWORD': config('EMAIL_HOST_PASSWORD', default=''),
    }


def security_cookie_settings(*, secure: bool) -> dict[str, Any]:
    return {
        'CSRF_COOKIE_SECURE': secure,
        'SESSION_COOKIE_SECURE': secure,
    }


def reverse_proxy_https_settings(*, allowed_hosts: list[str]) -> dict[str, Any]:
    return {
        **security_cookie_settings(secure=True),
        'CSRF_TRUSTED_ORIGINS': [f'https://{host}' for host in allowed_hosts],
        'SECURE_PROXY_SSL_HEADER': ('HTTP_X_FORWARDED_PROTO', 'https'),
    }


def production_security_settings(*, allowed_hosts: list[str]) -> dict[str, Any]:
    return {
        **reverse_proxy_https_settings(allowed_hosts=allowed_hosts),
        'SECURE_SSL_REDIRECT': config('SECURE_SSL_REDIRECT', default=True, cast=bool),
        'SECURE_HSTS_SECONDS': config('SECURE_HSTS_SECONDS', default=31536000, cast=int),
        'SECURE_CONTENT_TYPE_NOSNIFF': True,
        'SESSION_COOKIE_HTTPONLY': True,
        'SESSION_COOKIE_SAMESITE': 'Strict',
        'CSRF_COOKIE_HTTPONLY': True,
        'CSRF_COOKIE_SAMESITE': 'Strict',
        'X_FRAME_OPTIONS': 'DENY',
    }


def ci_logging_settings() -> dict[str, Any]:
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'simple': {
                'format': '%(levelname)s %(name)s %(message)s',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'simple',
            },
        },
        'root': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
        'loggers': {
            'django': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
            'fair_genomes': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
            'warehouse': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
            'ticketing': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        },
    }
