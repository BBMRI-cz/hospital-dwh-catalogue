"""CI settings for automated checks and test execution."""

from . import base as base_settings
from .helpers import (
    build_sqlite_databases,
    ci_logging_settings,
    console_email_settings,
    security_cookie_settings,
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
LOG_REQUEST_ID_HEADER = base_settings.LOG_REQUEST_ID_HEADER
GENERATE_REQUEST_ID_IF_NOT_IN_HEADER = base_settings.GENERATE_REQUEST_ID_IF_NOT_IN_HEADER
LOG_SLOW_REQUEST_THRESHOLD_S = base_settings.LOG_SLOW_REQUEST_THRESHOLD_S
STATIC_URL = base_settings.STATIC_URL
STATIC_ROOT = base_settings.STATIC_ROOT
DEFAULT_AUTO_FIELD = base_settings.DEFAULT_AUTO_FIELD
HEALTH_DCAT_VERSION = base_settings.HEALTH_DCAT_VERSION
CATALOGUE_PAGE_SIZE = base_settings.CATALOGUE_PAGE_SIZE

SECRET_KEY = 'ci-secret-key-not-for-production'
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']
SITE_URL = 'http://testserver'

DATABASES = build_sqlite_databases(BASE_DIR)

MOCK_LDAP = True
AUTHENTICATION_BACKENDS = [
    'catalogue.mock_ldap.MockLDAPBackend',
    'django.contrib.auth.backends.ModelBackend',
]

MOCK_FAIR_GENOMES = True
FAIR_GENOMES_RDF_URL = ''
FAIR_GENOMES_API_URL = ''
FAIR_GENOMES_API_TOKEN = ''
FAIR_GENOMES_SYNC_INTERVAL_HOURS = 24

MOCK_ALVAO = True
ALVAO_API_URL = ''
ALVAO_SERVICE_ACCOUNT_USERNAME = ''
ALVAO_SERVICE_ACCOUNT_PASSWORD = ''
ALVAO_DEFAULT_SERVICE_ID = None

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

_EMAIL_SETTINGS = console_email_settings()
EMAIL_BACKEND = _EMAIL_SETTINGS['EMAIL_BACKEND']

_SECURITY_SETTINGS = security_cookie_settings(secure=False)
CSRF_COOKIE_SECURE = _SECURITY_SETTINGS['CSRF_COOKIE_SECURE']
SESSION_COOKIE_SECURE = _SECURITY_SETTINGS['SESSION_COOKIE_SECURE']

LOGGING = ci_logging_settings()
