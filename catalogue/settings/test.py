"""
Test environment settings for catalogue project.
Configuration for remote testing server.
"""

from .base import *
from decouple import config, Csv

# Debug should be True for testing but can be toggled
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='', cast=Csv())


# Email backend for testing
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Logging configuration for testing
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
        'file': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'test.log'),
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Test-specific security settings (less strict than production)
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
