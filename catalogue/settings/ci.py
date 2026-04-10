"""CI settings for automated checks and test execution."""

from .base import *

SECRET_KEY = 'ci-secret-key-not-for-production'
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']
SITE_URL = 'http://testserver'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test_db.sqlite3',
    },
    'auth_db': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test_auth_db.sqlite3',
    },
    'metadata_db': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test_metadata_db.sqlite3',
    },
    'fair_genomes_db': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test_fair_genomes_db.sqlite3',
    },
}

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

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

LOGGING = {
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
