"""Development settings for local developer machines."""

from decouple import config

from .base import *

SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-change-me')
DEBUG = True
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='localhost,127.0.0.1,0.0.0.0',
    cast=lambda v: [s.strip() for s in v.split(',')],
)
SITE_URL = str(config('SITE_URL', default='http://localhost')).rstrip('/')


def _postgres_db(
    name_var: str,
    user_var: str,
    password_var: str,
    host_var: str,
    port_var: str,
    *,
    name_default: str,
    user_default: str = 'root',
    password_default: str = 'dwh_password',
    host_default: str = 'db',
    port_default: str = '5432',
):
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config(name_var, default=name_default),
        'USER': config(user_var, default=user_default),
        'PASSWORD': config(password_var, default=password_default),
        'HOST': config(host_var, default=host_default),
        'PORT': config(port_var, default=port_default),
        'OPTIONS': {'connect_timeout': 30},
    }


DATABASES = {
    'default': _postgres_db(
        'POSTGRES_DB',
        'POSTGRES_USER',
        'POSTGRES_PASSWORD',
        'POSTGRES_HOST',
        'POSTGRES_PORT',
        name_default='dwhi_dev',
    ),
    'auth_db': _postgres_db(
        'AUTH_DB_NAME',
        'AUTH_DB_USER',
        'AUTH_DB_PASSWORD',
        'AUTH_DB_HOST',
        'AUTH_DB_PORT',
        name_default='hospital_dwh_auth',
    ),
    'metadata_db': _postgres_db(
        'METADATA_DB_NAME',
        'METADATA_DB_USER',
        'METADATA_DB_PASSWORD',
        'METADATA_DB_HOST',
        'METADATA_DB_PORT',
        name_default='dwhi_dev',
    ),
    'fair_genomes_db': _postgres_db(
        'FAIR_GENOMES_DB_NAME',
        'FAIR_GENOMES_DB_USER',
        'FAIR_GENOMES_DB_PASSWORD',
        'FAIR_GENOMES_DB_HOST',
        'FAIR_GENOMES_DB_PORT',
        name_default='fair_genomes',
    ),
}

MOCK_LDAP = config('MOCK_LDAP', default=True, cast=bool)
if MOCK_LDAP:
    AUTHENTICATION_BACKENDS = [
        'catalogue.mock_ldap.MockLDAPBackend',
        'django.contrib.auth.backends.ModelBackend',
    ]
else:
    import ldap
    from django_auth_ldap.config import LDAPSearch

    ldap_attributes = vars(ldap)
    LDAP_SCOPE_SUBTREE = ldap_attributes['SCOPE_SUBTREE']
    LDAP_OPT_REFERRALS = ldap_attributes['OPT_REFERRALS']
    LDAP_OPT_NETWORK_TIMEOUT = ldap_attributes['OPT_NETWORK_TIMEOUT']

    AUTHENTICATION_BACKENDS = [
        'django_auth_ldap.backend.LDAPBackend',
        'django.contrib.auth.backends.ModelBackend',
    ]
    AUTH_LDAP_SERVER_URI = config('AUTH_LDAP_SERVER_URI')
    AUTH_LDAP_BIND_DN = config('AUTH_LDAP_BIND_DN')
    AUTH_LDAP_BIND_PASSWORD = config('AUTH_LDAP_BIND_PASSWORD')
    AUTH_LDAP_USER_SEARCH_BASE = config('AUTH_LDAP_USER_SEARCH_BASE')
    AUTH_LDAP_USER_SEARCH = LDAPSearch(
        AUTH_LDAP_USER_SEARCH_BASE,
        LDAP_SCOPE_SUBTREE,
        '(sAMAccountName=%(user)s)',
    )
    AUTH_LDAP_USER_ATTR_MAP = {
        'first_name': 'givenName',
        'last_name': 'sn',
        'email': 'mail',
    }
    AUTH_LDAP_ALWAYS_UPDATE_USER = True
    AUTH_LDAP_CONNECTION_OPTIONS = {
        LDAP_OPT_REFERRALS: 0,
        LDAP_OPT_NETWORK_TIMEOUT: 30,
    }
    AUTH_LDAP_START_TLS = config('AUTH_LDAP_START_TLS', default=False, cast=bool)

MOCK_FAIR_GENOMES = config('MOCK_FAIR_GENOMES', default=True, cast=bool)
if MOCK_FAIR_GENOMES:
    FAIR_GENOMES_RDF_URL = config('FAIR_GENOMES_RDF_URL', default='')
    FAIR_GENOMES_API_URL = config('FAIR_GENOMES_API_URL', default='')
    FAIR_GENOMES_API_TOKEN = config('FAIR_GENOMES_API_TOKEN', default='')
else:
    FAIR_GENOMES_RDF_URL = config('FAIR_GENOMES_RDF_URL')
    FAIR_GENOMES_API_URL = config('FAIR_GENOMES_API_URL')
    FAIR_GENOMES_API_TOKEN = config('FAIR_GENOMES_API_TOKEN')
FAIR_GENOMES_SYNC_INTERVAL_HOURS = config('FAIR_GENOMES_SYNC_INTERVAL_HOURS', default=24, cast=int)

MOCK_ALVAO = config('MOCK_ALVAO', default=True, cast=bool)
if MOCK_ALVAO:
    ALVAO_API_URL = config('ALVAO_API_URL', default='')
    ALVAO_SERVICE_ACCOUNT_USERNAME = config('ALVAO_SERVICE_ACCOUNT_USERNAME', default='')
    ALVAO_SERVICE_ACCOUNT_PASSWORD = config('ALVAO_SERVICE_ACCOUNT_PASSWORD', default='')
    ALVAO_DEFAULT_SERVICE_ID = config(
        'ALVAO_DEFAULT_SERVICE_ID', default=None, cast=lambda x: int(x) if x else None
    )
else:
    ALVAO_API_URL = config('ALVAO_API_URL')
    ALVAO_SERVICE_ACCOUNT_USERNAME = config('ALVAO_SERVICE_ACCOUNT_USERNAME')
    ALVAO_SERVICE_ACCOUNT_PASSWORD = config('ALVAO_SERVICE_ACCOUNT_PASSWORD')
    ALVAO_DEFAULT_SERVICE_ID = config('ALVAO_DEFAULT_SERVICE_ID', cast=int)

INSTALLED_APPS += [
    # Add development tools here, e.g.:
    # 'debug_toolbar',
]

INTERNAL_IPS = ['127.0.0.1']

_REDIS_URL = config('REDIS_URL', default='')
if _REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': _REDIS_URL,
            'KEY_PREFIX': 'catalogue_dev',
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'IGNORE_EXCEPTIONS': True,
            },
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
