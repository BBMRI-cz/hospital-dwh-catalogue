"""
Ticketing application configuration.
"""
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class TicketingConfig(AppConfig):
    """Configuration for the ticketing application."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ticketing'
    verbose_name = _('Ticketing')
