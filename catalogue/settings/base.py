"""Base settings shared by all runtime environments."""

import os
from pathlib import Path

from decouple import config

from django.utils.translation import gettext_lazy as _

from .helpers import positive_int_or_default

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Environment-specific modules must define runtime configuration such as
# SECRET_KEY, DEBUG, ALLOWED_HOSTS, SITE_URL, DATABASES,
# AUTHENTICATION_BACKENDS, and external service settings.

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'frontend',
    'warehouse',
    'fair_genomes',
    'ticketing',
    'schema_registry',
]

MIDDLEWARE = [
    'log_request_id.middleware.RequestIDMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'catalogue.middleware.RequestLoggingMiddleware',
    'catalogue.middleware.HtmxLoginRedirectMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'catalogue.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'frontend', 'templates')],
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

DATABASES = {}

DATABASE_ROUTERS = ['catalogue.routers.AuthRouter', 'catalogue.routers.WarehouseRouter']

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = 'login'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'cs'

LANGUAGES = [
    ('cs', _('Czech')),
    ('en', _('English')),
]

LOCALE_PATHS = [os.path.join(BASE_DIR, 'locale')]

TIME_ZONE = 'Europe/Prague'
USE_I18N = True
USE_TZ = True

LOG_DIR = str(config('LOG_DIR', default=str(BASE_DIR / 'logs')))
os.makedirs(LOG_DIR, exist_ok=True)

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
            'filename': os.path.join(LOG_DIR, 'app.log'),
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 10,
            'formatter': 'json',
            'filters': ['request_id'],
        },
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'error.log'),
            'maxBytes': 1024 * 1024 * 10,
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
        'django.server': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'WARNING',
            'propagate': False,
        },
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

LOG_REQUEST_ID_HEADER = 'HTTP_X_REQUEST_ID'
GENERATE_REQUEST_ID_IF_NOT_IN_HEADER = True
LOG_SLOW_REQUEST_THRESHOLD_S = config('LOG_SLOW_REQUEST_THRESHOLD_S', default=1.0, cast=float)

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

HEALTH_DCAT_VERSION = config('HEALTH_DCAT_VERSION', default='release-6')
CATALOGUE_PAGE_SIZE_DEFAULT = 15
CATALOGUE_PAGE_SIZE = config(
    'CATALOGUE_PAGE_SIZE',
    default=CATALOGUE_PAGE_SIZE_DEFAULT,
    cast=lambda value: positive_int_or_default(value, default=CATALOGUE_PAGE_SIZE_DEFAULT),
)
