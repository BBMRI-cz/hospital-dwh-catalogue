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
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
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
        'USER': config('AUTH_DB_USER'),
        'PASSWORD': config('AUTH_DB_PASSWORD'),
        'HOST': config('AUTH_DB_HOST'),
        'PORT': config('AUTH_DB_PORT', default='5432'),
        'OPTIONS': {
            'connect_timeout': 30,
        },
    },
    'metadata_db': {
        'ENGINE': config('METADATA_DB_ENGINE', default='django.db.backends.postgresql'),
        'NAME': config('METADATA_DB_NAME'),
        'USER': config('METADATA_DB_USER'),
        'PASSWORD': config('METADATA_DB_PASSWORD'),
        'HOST': config('METADATA_DB_HOST'),
        'PORT': config('METADATA_DB_PORT', default='5432'),
        'OPTIONS': {
            'connect_timeout': 30,
        },
    },
    'fair_genomes_db': {
        'ENGINE': config('FAIR_GENOMES_DB_ENGINE', default='django.db.backends.postgresql'),
        'NAME': config('FAIR_GENOMES_DB_NAME', default='fair_genomes'),
        'USER': config('FAIR_GENOMES_DB_USER', default='postgres'),
        'PASSWORD': config('FAIR_GENOMES_DB_PASSWORD'),
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
AUTH_USE_MOCK_LDAP = config('AUTH_USE_MOCK_LDAP', default=False, cast=bool)

# Build authentication backends list based on configuration
AUTHENTICATION_BACKENDS = []

if AUTH_USE_MOCK_LDAP:
    # Development: Use mock LDAP (accepts any credentials)
    AUTHENTICATION_BACKENDS.append('catalogue.mock_ldap.MockLDAPBackend')
else:
    # Production: Use real LDAP/AD authentication
    try:
        import django_auth_ldap
        AUTHENTICATION_BACKENDS.append('django_auth_ldap.backend.LDAPBackend')
    except ImportError:
        import logging
        logging.warning('django-auth-ldap not installed. LDAP authentication unavailable.')

# Always include ModelBackend as fallback (for superuser access)
AUTHENTICATION_BACKENDS.append('django.contrib.auth.backends.ModelBackend')

# Mock LDAP Configuration (Development Only)
# Set to True to use mock LDAP backend instead of real AD

# Login/Logout URLs
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = 'login'


# Active Directory / LDAP Configuration (Production only)
# Only loaded when AUTH_USE_MOCK_LDAP=False
if not AUTH_USE_MOCK_LDAP:
    try:
        import ldap
        from django_auth_ldap.config import LDAPSearch, GroupOfNamesType

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
    except ImportError:
        import logging
        logging.warning('python-ldap not installed. Real LDAP authentication unavailable.')



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


# Logging base configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
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
        'level': 'INFO',
    },
}


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = '/static/'

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')


# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Fair Genomes GraphQL API Configuration
FAIR_GENOMES_API_URL = config('FAIR_GENOMES_API_URL')
FAIR_GENOMES_API_TOKEN = config('FAIR_GENOMES_API_TOKEN')
FAIR_GENOMES_FETCH_ON_STARTUP = config('FAIR_GENOMES_FETCH_ON_STARTUP', default=False, cast=bool)
FAIR_GENOMES_SYNC_INTERVAL_HOURS = config('FAIR_GENOMES_SYNC_INTERVAL_HOURS', default=24, cast=int)


# Alvao Service Desk Configuration
# Set ALVAO_USE_MOCK=True for development without real Alvao server
ALVAO_USE_MOCK = config('ALVAO_USE_MOCK', default=False, cast=bool)

# Real Alvao API settings (used when ALVAO_USE_MOCK=False)
ALVAO_API_URL = config('ALVAO_API_URL', default='')
ALVAO_API_TOKEN = config('ALVAO_API_TOKEN', default='')

# Alternative: Basic authentication (if token not available)
ALVAO_SERVICE_ACCOUNT_USERNAME = config('ALVAO_SERVICE_ACCOUNT_USERNAME', default='')
ALVAO_SERVICE_ACCOUNT_PASSWORD = config('ALVAO_SERVICE_ACCOUNT_PASSWORD', default='')

# Default service ID for new tickets (optional)
ALVAO_DEFAULT_SERVICE_ID = config(
    'ALVAO_DEFAULT_SERVICE_ID', default=None, cast=lambda x: int(x) if x else None
)
