"""
Mock LDAP authentication backend for development.

This module provides a fake LDAP authentication that accepts any
username/password combination for easy testing without a real AD server.
"""

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
    """
    Mock LDAP authentication backend for development.

    Accepts any non-empty username/password combination.
    Creates Django users automatically with generated attributes.

    Controlled by MOCK_LDAP setting.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate with mock LDAP - accepts any credentials.

        Args:
            request: HTTP request object
            username: Username to authenticate
            password: Password (any non-empty value accepted)

        Returns:
            User instance if authentication succeeds, None otherwise
        """
        # Only active if MOCK_LDAP is True
        if not getattr(settings, 'MOCK_LDAP', False):
            return None

        if not username or not password:
            return None

        logger.info(f'Mock LDAP: Authenticated {username}')

        # Get or create user - Django router will direct to correct database
        superuser_username = os.environ.get('DJANGO_SUPERUSER_USERNAME', '').strip()
        is_admin = bool(superuser_username) and username == superuser_username

        try:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': username.capitalize(),
                    'last_name': 'User',
                    'email': f'{username}@example.com',
                    'is_staff': is_admin,
                    'is_superuser': is_admin,
                },
            )
            user = cast(AbstractUser, user)

            if created:
                logger.info(f'Mock LDAP: Created new user {username}')
            else:
                logger.debug(f'Mock LDAP: User {username} already exists')
                if is_admin and not user.is_staff:
                    user.is_staff = True
                    user.is_superuser = True
                    user.save(update_fields=['is_staff', 'is_superuser'])
                    logger.info(f'Mock LDAP: Granted staff/superuser to {username}')

            return user

        except Exception as e:
            logger.exception(f'Mock LDAP: Error creating/updating user {username}: {e}')
            return None
