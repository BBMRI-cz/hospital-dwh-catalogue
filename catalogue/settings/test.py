"""
Test environment settings for catalogue project.
Configuration for CI/CD and local testing.
"""

from decouple import config

from .base import *

# Override security key for tests
SECRET_KEY = config('SECRET_KEY', default='test-secret-key-not-for-production')

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

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

# Fair Genomes API settings (mocked in tests)
FAIR_GENOMES_FETCH_ON_STARTUP = False

# Alvao settings (always use mock in tests)
ALVAO_USE_MOCK = True

# Email backend for testing
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Logging configuration for testing (console only - no file writes in CI)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Test-specific security settings (less strict than production)
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
