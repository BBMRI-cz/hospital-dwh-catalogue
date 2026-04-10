"""Production settings for the live deployment."""

from decouple import config

from .base import *

SECRET_KEY = config('SECRET_KEY')
DEBUG = False
ALLOWED_HOSTS: list[str] = config(  # type: ignore[assignment]
    'ALLOWED_HOSTS', cast=lambda v: [s.strip() for s in v.split(',')]
)
SITE_URL = str(config('SITE_URL')).rstrip('/')


def _postgres_db(
    name_var: str,
    user_var: str,
    password_var: str,
    host_var: str,
    port_var: str,
):
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config(name_var),
        'USER': config(user_var),
        'PASSWORD': config(password_var),
        'HOST': config(host_var),
        'PORT': config(port_var, default='5432'),
        'OPTIONS': {'connect_timeout': 30},
    }


DATABASES = {
    'default': _postgres_db(
        'POSTGRES_DB',
        'POSTGRES_USER',
        'POSTGRES_PASSWORD',
        'POSTGRES_HOST',
        'POSTGRES_PORT',
    ),
    'auth_db': _postgres_db(
        'AUTH_DB_NAME',
        'AUTH_DB_USER',
        'AUTH_DB_PASSWORD',
        'AUTH_DB_HOST',
        'AUTH_DB_PORT',
    ),
    'metadata_db': _postgres_db(
        'METADATA_DB_NAME',
        'METADATA_DB_USER',
        'METADATA_DB_PASSWORD',
        'METADATA_DB_HOST',
        'METADATA_DB_PORT',
    ),
    'fair_genomes_db': _postgres_db(
        'FAIR_GENOMES_DB_NAME',
        'FAIR_GENOMES_DB_USER',
        'FAIR_GENOMES_DB_PASSWORD',
        'FAIR_GENOMES_DB_HOST',
        'FAIR_GENOMES_DB_PORT',
    ),
}

MOCK_LDAP = False

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

MOCK_FAIR_GENOMES = False
FAIR_GENOMES_RDF_URL = config('FAIR_GENOMES_RDF_URL')
FAIR_GENOMES_API_URL = config('FAIR_GENOMES_API_URL')
FAIR_GENOMES_API_TOKEN = config('FAIR_GENOMES_API_TOKEN')
FAIR_GENOMES_SYNC_INTERVAL_HOURS = config('FAIR_GENOMES_SYNC_INTERVAL_HOURS', default=24, cast=int)

MOCK_ALVAO = False
ALVAO_API_URL = config('ALVAO_API_URL')
ALVAO_SERVICE_ACCOUNT_USERNAME = config('ALVAO_SERVICE_ACCOUNT_USERNAME')
ALVAO_SERVICE_ACCOUNT_PASSWORD = config('ALVAO_SERVICE_ACCOUNT_PASSWORD')
ALVAO_DEFAULT_SERVICE_ID = config('ALVAO_DEFAULT_SERVICE_ID', cast=int)

CSRF_TRUSTED_ORIGINS = [f'https://{host}' for host in ALLOWED_HOSTS]
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Strict'
X_FRAME_OPTIONS = 'DENY'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://redis:6379/1'),
        'KEY_PREFIX': 'catalogue',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {'max_connections': 20},
            'IGNORE_EXCEPTIONS': True,
        },
    }
}
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

ADMINS = [('Admin', config('ADMIN_EMAIL', default='admin@example.com'))]
MANAGERS = ADMINS
