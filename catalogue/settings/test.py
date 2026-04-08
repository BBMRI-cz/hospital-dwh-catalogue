"""
Test environment settings for catalogue project.
Configuration for CI/CD and local testing.
"""

from decouple import config

from .base import *

# Override security key for tests
SECRET_KEY = config('SECRET_KEY', default='test-secret-key-not-for-production')

DEBUG = True

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='localhost,127.0.0.1',
    cast=lambda v: [s.strip() for s in v.split(',')],
)

# Use SQLite for all databases in CI/testing for simplicity
USE_SQLITE = config('USE_SQLITE', default=True, cast=bool)

if USE_SQLITE:
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

# Cache — use real Redis when REDIS_URL is provided (server test stack),
# fall back to LocMemCache for CI where no Redis container is present.
_REDIS_URL = config('REDIS_URL', default='')

if _REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': _REDIS_URL,
            'KEY_PREFIX': 'catalogue_test',
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

# Alvao settings (always use mock in tests)
MOCK_ALVAO = True

# Email backend for testing
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Test-specific security settings (less strict than production)
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# Disable file-based log handlers in tests — log files are owned by root in
# Docker containers and are not writable by the developer's OS user.
# All loggers fall back to console only.
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
