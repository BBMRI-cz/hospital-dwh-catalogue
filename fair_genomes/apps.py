"""Fair Genomes application configuration."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class FairGenomesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fair_genomes'
    verbose_name = _('Fair Genomes Integration')
