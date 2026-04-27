"""Mock LDAP authentication for local development."""

import logging
import os
from typing import cast

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import AbstractUser

logger = logging.getLogger(__name__)

User = get_user_model()


class MockLDAPBackend(ModelBackend):
    """Authenticate against a local mock backend when enabled."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        """Accept any non-empty credentials while ``MOCK_LDAP`` is enabled."""
        if not getattr(settings, 'MOCK_LDAP', False):
            return None

        if not username or not password:
            return None

        logger.info('Mock LDAP authenticated %s', username)

        superuser_username = os.environ.get('DJANGO_SUPERUSER_USERNAME', '').strip()
        is_superuser = bool(superuser_username) and username == superuser_username

        try:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': username.capitalize(),
                    'last_name': 'User',
                    'email': f'{username}@example.com',
                    'is_staff': is_superuser,
                    'is_superuser': is_superuser,
                },
            )
            user = cast(AbstractUser, user)

            if created:
                logger.info('Mock LDAP created user %s', username)
            else:
                logger.debug('Mock LDAP found existing user %s', username)
                if is_superuser and not user.is_staff:
                    user.is_staff = True
                    user.is_superuser = True
                    user.save(update_fields=['is_staff', 'is_superuser'])
                    logger.info('Mock LDAP granted staff access to %s', username)

            return user

        except Exception:
            logger.exception('Mock LDAP failed to create or update %s', username)
            return None
