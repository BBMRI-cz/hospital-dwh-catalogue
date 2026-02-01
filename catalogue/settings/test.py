"""
Test environment settings for catalogue project.
Configuration for CI/CD and local testing.
"""

import os
from pathlib import Path

from decouple import Csv, config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Security settings
SECRET_KEY = config('SECRET_KEY', default='test-secret-key-not-for-production')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

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

# Use SQLite for all databases in CI/testing for simplicity
USE_SQLITE = config('USE_SQLITE', default=False, cast=bool)

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
else:
    # Use PostgreSQL databases from environment (for integration tests)
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
        },
        'metadata_db': {
            'ENGINE': config('METADATA_DB_ENGINE', default='django.db.backends.postgresql'),
            'NAME': config('METADATA_DB_NAME', default='hospital_dwh'),
            'USER': config('METADATA_DB_USER', default='postgres'),
            'PASSWORD': config('METADATA_DB_PASSWORD', default=''),
            'HOST': config('METADATA_DB_HOST', default='localhost'),
            'PORT': config('METADATA_DB_PORT', default='5432'),
        },
        'fair_genomes_db': {
            'ENGINE': config('FAIR_GENOMES_DB_ENGINE', default='django.db.backends.postgresql'),
            'NAME': config('FAIR_GENOMES_DB_NAME', default='fair_genomes'),
            'USER': config('FAIR_GENOMES_DB_USER', default='postgres'),
            'PASSWORD': config('FAIR_GENOMES_DB_PASSWORD', default=''),
            'HOST': config('FAIR_GENOMES_DB_HOST', default='localhost'),
            'PORT': config('FAIR_GENOMES_DB_PORT', default='5432'),
        },
    }

DATABASE_ROUTERS = ['catalogue.routers.AuthRouter', 'catalogue.routers.WarehouseRouter']

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
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

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Fair Genomes API settings (mocked in tests)
FAIR_GENOMES_API_URL = config(
    'FAIR_GENOMES_API_URL', default='https://mock-api.example.com/graphql'
)
FAIR_GENOMES_API_TOKEN = config('FAIR_GENOMES_API_TOKEN', default='mock-token')
FAIR_GENOMES_FETCH_ON_STARTUP = False
FAIR_GENOMES_SYNC_INTERVAL_HOURS = 24

# Alvao settings (use mock in tests)
ALVAO_USE_MOCK = True
ALVAO_API_URL = ''
ALVAO_API_TOKEN = ''
ALVAO_SERVICE_ACCOUNT_USERNAME = ''
ALVAO_SERVICE_ACCOUNT_PASSWORD = ''
ALVAO_DEFAULT_SERVICE_ID = None

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
