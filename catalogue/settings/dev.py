"""Development settings for local developer machines."""

from decouple import config

from . import base as base_settings
from .helpers import (
    alvao_settings,
    build_postgres_databases,
    cache_settings,
    console_email_settings,
    env_list,
    fair_genomes_settings,
    ldap_settings,
)

BASE_DIR = base_settings.BASE_DIR
INSTALLED_APPS = [*base_settings.INSTALLED_APPS]
MIDDLEWARE = base_settings.MIDDLEWARE
ROOT_URLCONF = base_settings.ROOT_URLCONF
TEMPLATES = base_settings.TEMPLATES
WSGI_APPLICATION = base_settings.WSGI_APPLICATION
DATABASE_ROUTERS = base_settings.DATABASE_ROUTERS
LOGIN_URL = base_settings.LOGIN_URL
LOGIN_REDIRECT_URL = base_settings.LOGIN_REDIRECT_URL
LOGOUT_REDIRECT_URL = base_settings.LOGOUT_REDIRECT_URL
AUTH_PASSWORD_VALIDATORS = base_settings.AUTH_PASSWORD_VALIDATORS
LANGUAGE_CODE = base_settings.LANGUAGE_CODE
LANGUAGES = base_settings.LANGUAGES
LOCALE_PATHS = base_settings.LOCALE_PATHS
TIME_ZONE = base_settings.TIME_ZONE
USE_I18N = base_settings.USE_I18N
USE_TZ = base_settings.USE_TZ
LOG_DIR = base_settings.LOG_DIR
LOGGING = base_settings.LOGGING
LOG_REQUEST_ID_HEADER = base_settings.LOG_REQUEST_ID_HEADER
GENERATE_REQUEST_ID_IF_NOT_IN_HEADER = base_settings.GENERATE_REQUEST_ID_IF_NOT_IN_HEADER
LOG_SLOW_REQUEST_THRESHOLD_S = base_settings.LOG_SLOW_REQUEST_THRESHOLD_S
STATIC_URL = base_settings.STATIC_URL
STATIC_ROOT = base_settings.STATIC_ROOT
DEFAULT_AUTO_FIELD = base_settings.DEFAULT_AUTO_FIELD
HEALTH_DCAT_VERSION = base_settings.HEALTH_DCAT_VERSION
CATALOGUE_PAGE_SIZE = base_settings.CATALOGUE_PAGE_SIZE

SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-change-me')
DEBUG = True
ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', default='localhost,127.0.0.1,0.0.0.0')
SITE_URL = str(config('SITE_URL', default='http://localhost')).rstrip('/')

DATABASES = build_postgres_databases(
    defaults={
        'default': {
            'name_default': 'dwhi_dev',
            'user_default': 'root',
            'password_default': 'dwh_password',
            'host_default': 'db',
        },
        'auth_db': {
            'name_default': 'hospital_dwh_auth',
            'user_default': 'root',
            'password_default': 'dwh_password',
            'host_default': 'db',
        },
        'metadata_db': {
            'name_default': 'dwhi_dev',
            'user_default': 'root',
            'password_default': 'dwh_password',
            'host_default': 'db',
        },
        'fair_genomes_db': {
            'name_default': 'fair_genomes',
            'user_default': 'root',
            'password_default': 'dwh_password',
            'host_default': 'db',
        },
    }
)

MOCK_LDAP = config('MOCK_LDAP', default=True, cast=bool)
_LDAP_SETTINGS = ldap_settings(mock_ldap=MOCK_LDAP)
globals().update(_LDAP_SETTINGS)

MOCK_FAIR_GENOMES = config('MOCK_FAIR_GENOMES', default=True, cast=bool)
_FAIR_GENOMES_SETTINGS = fair_genomes_settings(mock_fair_genomes=MOCK_FAIR_GENOMES)
FAIR_GENOMES_RDF_URL = _FAIR_GENOMES_SETTINGS['FAIR_GENOMES_RDF_URL']
FAIR_GENOMES_API_URL = _FAIR_GENOMES_SETTINGS['FAIR_GENOMES_API_URL']
FAIR_GENOMES_API_TOKEN = _FAIR_GENOMES_SETTINGS['FAIR_GENOMES_API_TOKEN']
FAIR_GENOMES_SYNC_INTERVAL_HOURS = _FAIR_GENOMES_SETTINGS['FAIR_GENOMES_SYNC_INTERVAL_HOURS']

MOCK_ALVAO = config('MOCK_ALVAO', default=True, cast=bool)
_ALVAO_SETTINGS = alvao_settings(mock_alvao=MOCK_ALVAO)
ALVAO_API_URL = _ALVAO_SETTINGS['ALVAO_API_URL']
ALVAO_SERVICE_ACCOUNT_USERNAME = _ALVAO_SETTINGS['ALVAO_SERVICE_ACCOUNT_USERNAME']
ALVAO_SERVICE_ACCOUNT_PASSWORD = _ALVAO_SETTINGS['ALVAO_SERVICE_ACCOUNT_PASSWORD']
ALVAO_TEST_REQUESTER_EMAIL = _ALVAO_SETTINGS['ALVAO_TEST_REQUESTER_EMAIL']
ALVAO_TEST_REQUESTER_NAME = _ALVAO_SETTINGS['ALVAO_TEST_REQUESTER_NAME']
ALVAO_DEFAULT_SERVICE_ID = _ALVAO_SETTINGS['ALVAO_DEFAULT_SERVICE_ID']

INTERNAL_IPS = ['127.0.0.1']

_CACHE_SETTINGS = cache_settings(key_prefix='catalogue_dev')
CACHES = _CACHE_SETTINGS['CACHES']
SESSION_ENGINE = _CACHE_SETTINGS.get(
    'SESSION_ENGINE',
    'django.contrib.sessions.backends.db',
)
if 'SESSION_CACHE_ALIAS' in _CACHE_SETTINGS:
    SESSION_CACHE_ALIAS = _CACHE_SETTINGS['SESSION_CACHE_ALIAS']

_EMAIL_SETTINGS = console_email_settings()
EMAIL_BACKEND = _EMAIL_SETTINGS['EMAIL_BACKEND']
