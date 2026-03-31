"""
Base settings for catalogue project.
Shared settings used across all environments.
"""

import os
from pathlib import Path

from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-change-in-production')

DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=lambda v: [s.strip() for s in v.split(',')]
)

# Public base URL used for building absolute URIs in JSON-LD export.
# Set SITE_URL in the environment (.env / docker-compose) for each deployment.
SITE_URL = config('SITE_URL', default='http://localhost:8000')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    # My apps
    'warehouse',
    'fair_genomes',
    'ticketing',
    'schema_registry',  # kept for app registry / admin; no DB models
]

MIDDLEWARE = [
    'log_request_id.middleware.RequestIDMiddleware',  # must be first — stamps request_id on every log record
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'catalogue.middleware.RequestLoggingMiddleware',  # after auth so request.user is available
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'catalogue.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'warehouse', 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.i18n',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'ticketing.context_processors.cart_count',
            ],
        },
        'NAME': 'django',
    },
]

WSGI_APPLICATION = 'catalogue.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    },
    'auth_db': {
        'ENGINE': config('AUTH_DB_ENGINE', default='django.db.backends.postgresql'),
        'NAME': config('AUTH_DB_NAME', default='hospital_dwh_auth'),
        'USER': config('AUTH_DB_USER', default='postgres'),
        'PASSWORD': config('AUTH_DB_PASSWORD', default=''),
        'HOST': config('AUTH_DB_HOST', default='localhost'),
        'PORT': config('AUTH_DB_PORT', default='5432'),
        'OPTIONS': {
            'connect_timeout': 30,
        },
    },
    'metadata_db': {
        'ENGINE': config('METADATA_DB_ENGINE', default='django.db.backends.postgresql'),
        'NAME': config('METADATA_DB_NAME', default='hospital_dwh'),
        'USER': config('METADATA_DB_USER', default='postgres'),
        'PASSWORD': config('METADATA_DB_PASSWORD', default=''),
        'HOST': config('METADATA_DB_HOST', default='localhost'),
        'PORT': config('METADATA_DB_PORT', default='5432'),
        'OPTIONS': {
            'connect_timeout': 30,
        },
    },
    'fair_genomes_db': {
        'ENGINE': config('FAIR_GENOMES_DB_ENGINE', default='django.db.backends.postgresql'),
        'NAME': config('FAIR_GENOMES_DB_NAME', default='fair_genomes'),
        'USER': config('FAIR_GENOMES_DB_USER', default='postgres'),
        'PASSWORD': config('FAIR_GENOMES_DB_PASSWORD', default=''),
        'HOST': config('FAIR_GENOMES_DB_HOST', default='localhost'),
        'PORT': config('FAIR_GENOMES_DB_PORT', default='5432'),
        'OPTIONS': {
            'connect_timeout': 30,
        },
    },
}

DATABASE_ROUTERS = ['catalogue.routers.AuthRouter', 'catalogue.routers.WarehouseRouter']


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

# Authentication backends
# Configure based on environment: mock for dev, real LDAP for prod
MOCK_LDAP = config('MOCK_LDAP', default=False, cast=bool)

# Build authentication backends list based on configuration
AUTHENTICATION_BACKENDS = []

if MOCK_LDAP:
    # Development: Use mock LDAP (accepts any credentials)
    AUTHENTICATION_BACKENDS.append('catalogue.mock_ldap.MockLDAPBackend')
else:
    # Production: Use real LDAP/AD authentication
    AUTHENTICATION_BACKENDS.append('django_auth_ldap.backend.LDAPBackend')

# Always include ModelBackend as fallback (for superuser access)
AUTHENTICATION_BACKENDS.append('django.contrib.auth.backends.ModelBackend')

# Login/Logout URLs
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = 'login'


# Active Directory / LDAP Configuration (Production only)
# Only loaded when MOCK_LDAP=False
if not MOCK_LDAP:
    import ldap
    from django_auth_ldap.config import GroupOfNamesType, LDAPSearch

    AUTH_LDAP_SERVER_URI = config('AUTH_LDAP_SERVER_URI', default='')
    AUTH_LDAP_BIND_DN = config('AUTH_LDAP_BIND_DN', default='')
    AUTH_LDAP_BIND_PASSWORD = config('AUTH_LDAP_BIND_PASSWORD', default='')

    # User search base (where to look for users in AD)
    AUTH_LDAP_USER_SEARCH_BASE = config('AUTH_LDAP_USER_SEARCH_BASE', default='dc=example,dc=com')
    AUTH_LDAP_USER_SEARCH = LDAPSearch(
        AUTH_LDAP_USER_SEARCH_BASE,
        ldap.SCOPE_SUBTREE,
        '(sAMAccountName=%(user)s)',  # Standard AD username attribute
    )

    # Populate Django user from LDAP attributes
    AUTH_LDAP_USER_ATTR_MAP = {
        'first_name': 'givenName',
        'last_name': 'sn',
        'email': 'mail',
    }

    # Auto-create users on first login
    AUTH_LDAP_ALWAYS_UPDATE_USER = True

    # LDAP Connection Options
    AUTH_LDAP_CONNECTION_OPTIONS = {
        ldap.OPT_REFERRALS: 0,
        ldap.OPT_NETWORK_TIMEOUT: 30,
    }

    # Use StartTLS for secure connection (if not using ldaps://)
    AUTH_LDAP_START_TLS = config('AUTH_LDAP_START_TLS', default=False, cast=bool)


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

from django.utils.translation import gettext_lazy as _

LANGUAGE_CODE = 'cs'

LANGUAGES = [
    ('cs', _('Czech')),
    ('en', _('English')),
]

LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]

TIME_ZONE = 'Europe/Prague'

USE_I18N = True

USE_TZ = True


# Logging — single shared configuration for all environments.
# Each env inherits this from base; do NOT override LOGGING in env-specific settings.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'request_id': {
            '()': 'log_request_id.filters.RequestIDFilter',
        },
    },
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'fmt': '%(asctime)s %(levelname)s %(name)s %(module)s %(process)d %(request_id)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
            'filters': ['request_id'],
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'app.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 10,
            'formatter': 'json',
            'filters': ['request_id'],
        },
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'error.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 10,
            'formatter': 'json',
            'filters': ['request_id'],
            'level': 'ERROR',
        },
    },
    'root': {
        'handlers': ['console', 'file', 'error_file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {'handlers': ['error_file'], 'level': 'ERROR', 'propagate': False},
        'django.security': {
            'handlers': ['console', 'error_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        # Suppress INFO access-log spam from Django's dev HTTP server — all requests are already
        # captured by catalogue.request (RequestLoggingMiddleware).  Keep WARNING so 4xx/5xx show.
        'django.server': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        # Suppress file-watcher polling from runserver's auto-reloader — not relevant in production.
        'django.utils.autoreload': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django_redis': {'handlers': ['error_file'], 'level': 'ERROR', 'propagate': False},
        'warehouse': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'ticketing': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'fair_genomes': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'schema_registry': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'catalogue': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'catalogue.request': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Request ID settings (django-log-request-id)
# Reads X-Request-ID from upstream (e.g. Nginx) and generates one if absent.
LOG_REQUEST_ID_HEADER = 'HTTP_X_REQUEST_ID'
GENERATE_REQUEST_ID_IF_NOT_IN_HEADER = True

# Slow request threshold (seconds) — requests exceeding this are logged at WARNING.
LOG_SLOW_REQUEST_THRESHOLD_S = config('LOG_SLOW_REQUEST_THRESHOLD_S', default=1.0, cast=float)


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = '/static/'

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')


# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Fair Genomes Integration Configuration
FAIR_GENOMES_RDF_URL = config('FAIR_GENOMES_RDF_URL', default='')
FAIR_GENOMES_API_URL = config('FAIR_GENOMES_API_URL', default='')  # GraphQL schema endpoint
FAIR_GENOMES_API_TOKEN = config('FAIR_GENOMES_API_TOKEN', default='')  # x-molgenis-token header
FAIR_GENOMES_SYNC_INTERVAL_HOURS = config('FAIR_GENOMES_SYNC_INTERVAL_HOURS', default=24, cast=int)


# Alvao Service Desk Configuration
# Set MOCK_ALVAO=True for development without real Alvao server
MOCK_ALVAO = config('MOCK_ALVAO', default=False, cast=bool)

# Real Alvao API settings (used when MOCK_ALVAO=False)
ALVAO_API_URL = config('ALVAO_API_URL', default='')
ALVAO_API_TOKEN = config('ALVAO_API_TOKEN', default='')

# Alternative: Basic authentication (if token not available)
ALVAO_SERVICE_ACCOUNT_USERNAME = config('ALVAO_SERVICE_ACCOUNT_USERNAME', default='')
ALVAO_SERVICE_ACCOUNT_PASSWORD = config('ALVAO_SERVICE_ACCOUNT_PASSWORD', default='')

# Default service ID for new tickets (optional)
ALVAO_DEFAULT_SERVICE_ID = config(
    'ALVAO_DEFAULT_SERVICE_ID', default=None, cast=lambda x: int(x) if x else None
)

# Mock Data Settings
# Set MOCK_FAIR_GENOMES=True to seed sample data into fair_genomes_db on startup
MOCK_FAIR_GENOMES = config('MOCK_FAIR_GENOMES', default=False, cast=bool)

# HealthDCAT-AP Schema Registry
# Directory name inside the health_dcat_ap/ git submodule (e.g. 'release-6').
# Run ./deploy.sh --update to fetch a newer version of the submodule.
HEALTH_DCAT_VERSION = config('HEALTH_DCAT_VERSION', default='release-6')
