"""
Base settings for catalogue project.
Shared settings used across all environments.
"""

from pathlib import Path
import os
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')


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
    'metadata_db': {
        'ENGINE': config('METADATA_DB_ENGINE', default='django.db.backends.postgresql'),
        'NAME': config('METADATA_DB_NAME'),
        'USER': config('METADATA_DB_USER'),
        'PASSWORD': config('METADATA_DB_PASSWORD'),
        'HOST': config('METADATA_DB_HOST'),
        'PORT': config('METADATA_DB_PORT', default='5432'),
        'OPTIONS': {
            'connect_timeout': 30,
        }
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
        }
    }
}

DATABASE_ROUTERS = ['catalogue.routers.WarehouseRouter']


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

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

# Note: USE_L10N is deprecated in Django 4.0+ and defaults to True
USE_L10N = True

USE_TZ = True


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

