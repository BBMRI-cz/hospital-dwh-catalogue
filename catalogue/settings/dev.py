"""
Development settings for catalogue project.
Local development environment configuration.
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']  # nosec B104 - acceptable for dev


# Development-specific apps
INSTALLED_APPS += [
    # Add development tools here, e.g.:
    # 'debug_toolbar',
]

# Development-specific middleware
# MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE

# Internal IPs for debug toolbar
INTERNAL_IPS = [
    '127.0.0.1',
]

# Cache — single-process in-memory; not shared across workers (dev/CI only)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
