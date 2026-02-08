"""Fair Genomes application configuration."""

import logging

from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class FairGenomesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fair_genomes'
    verbose_name = _('Fair Genomes Integration')

    def ready(self):
        """
        Application initialization.
        Called once when Django starts.
        """
        # Fetch Fair Genomes data on startup if enabled
        if getattr(settings, 'FAIR_GENOMES_FETCH_ON_STARTUP', False):
            self._fetch_fair_genomes_on_startup()

        # Start periodic scheduler if interval is configured
        sync_interval = getattr(settings, 'FAIR_GENOMES_SYNC_INTERVAL_HOURS', None)
        if sync_interval and sync_interval > 0:
            self._start_periodic_scheduler(sync_interval)

    def _fetch_fair_genomes_on_startup(self):
        """
        Fetch Fair Genomes data during application startup.
        Runs asynchronously to avoid blocking startup.
        """
        from threading import Thread

        def sync_in_background():
            """Background thread function to sync data."""
            try:
                logger.info('Starting Fair Genomes data sync on startup')
                from .services import FairGenomesService

                with FairGenomesService() as service:
                    stats = service.sync_personal_data(dry_run=False)

                logger.info(
                    f'Startup sync completed: {stats["created"]} created, '
                    f'{stats["updated"]} updated'
                )
            except Exception as e:
                logger.error(f'Startup sync failed: {e}', exc_info=True)

        # Run in background thread to not block Django startup
        thread = Thread(target=sync_in_background, daemon=True)
        thread.start()
        logger.info('Fair Genomes startup sync initiated in background')

    def _start_periodic_scheduler(self, interval_hours: int):
        """
        Start the periodic background scheduler.

        Args:
            interval_hours: Hours between sync runs
        """
        try:
            from .scheduler import start_scheduler

            start_scheduler(interval_hours=interval_hours)
            logger.info(
                f'Fair Genomes periodic scheduler started (interval: {interval_hours} hours)'
            )
        except Exception as e:
            logger.error(f'Failed to start Fair Genomes scheduler: {e}', exc_info=True)
