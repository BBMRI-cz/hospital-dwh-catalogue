"""
Background scheduler for periodic Fair Genomes data synchronization.
Simple threading-based scheduler without external dependencies.
"""
import logging
import time
from threading import Thread, Event
from typing import Optional

from django.conf import settings


logger = logging.getLogger(__name__)


class FairGenomesScheduler:
    """
    Simple background scheduler for periodic data synchronization.
    Runs in a daemon thread and executes sync at configurable intervals.
    """
    
    def __init__(self, interval_hours: Optional[int] = None):
        """
        Initialize the scheduler.
        
        Args:
            interval_hours: Hours between sync runs (default from settings)
        """
        self.interval_hours = interval_hours or getattr(
            settings, 'FAIR_GENOMES_SYNC_INTERVAL_HOURS', 24
        )
        self.interval_seconds = self.interval_hours * 3600
        self._thread: Optional[Thread] = None
        self._stop_event = Event()
        self._running = False
    
    def _sync_loop(self):
        """Background thread loop that performs periodic syncs."""
        logger.info(
            f"Fair Genomes scheduler started (interval: {self.interval_hours} hours)"
        )
        
        while not self._stop_event.is_set():
            try:
                # Wait for the interval (or until stop event is set)
                if self._stop_event.wait(timeout=self.interval_seconds):
                    break  # Stop event was set
                
                # Perform sync
                logger.info("Starting scheduled Fair Genomes data sync")
                self._perform_sync()
                
            except Exception as e:
                logger.error(
                    f"Error in scheduler loop: {e}",
                    exc_info=True
                )
                # Continue running even if sync fails
        
        logger.info("Fair Genomes scheduler stopped")
    
    def _perform_sync(self):
        """Execute the sync operation."""
        try:
            from .services import FairGenomesService
            
            with FairGenomesService() as service:
                stats = service.sync_personal_data(dry_run=False)
            
            logger.info(
                f"Scheduled sync completed: {stats['created']} created, "
                f"{stats['updated']} updated, {stats['failed']} failed"
            )
            
        except Exception as e:
            logger.error(
                f"Scheduled sync failed: {e}",
                exc_info=True
            )
    
    def start(self):
        """Start the background scheduler thread."""
        if self._running:
            logger.warning("Scheduler is already running")
            return
        
        self._stop_event.clear()
        self._thread = Thread(
            target=self._sync_loop,
            name="FairGenomesScheduler",
            daemon=True
        )
        self._thread.start()
        self._running = True
        
        logger.info(
            f"Fair Genomes scheduler thread started "
            f"(next sync in {self.interval_hours} hours)"
        )
    
    def stop(self, timeout: int = 5):
        """
        Stop the scheduler thread.
        
        Args:
            timeout: Seconds to wait for thread to stop
        """
        if not self._running:
            return
        
        logger.info("Stopping Fair Genomes scheduler...")
        self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        
        self._running = False
        logger.info("Fair Genomes scheduler stopped")
    
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running and self._thread and self._thread.is_alive()


# Global scheduler instance
_scheduler: Optional[FairGenomesScheduler] = None


def start_scheduler(interval_hours: Optional[int] = None):
    """
    Start the global scheduler instance.
    
    Args:
        interval_hours: Hours between sync runs
    """
    global _scheduler
    
    if _scheduler is not None and _scheduler.is_running():
        logger.warning("Scheduler already running")
        return
    
    _scheduler = FairGenomesScheduler(interval_hours=interval_hours)
    _scheduler.start()


def stop_scheduler(timeout: int = 5):
    """
    Stop the global scheduler instance.
    
    Args:
        timeout: Seconds to wait for shutdown
    """
    global _scheduler
    
    if _scheduler is not None:
        _scheduler.stop(timeout=timeout)
        _scheduler = None


def get_scheduler() -> Optional[FairGenomesScheduler]:
    """Get the global scheduler instance."""
    return _scheduler
