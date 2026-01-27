"""APScheduler-based briefing scheduler."""

import asyncio
from typing import TYPE_CHECKING

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from postal_inspector.briefing.generator import BriefingGenerator

if TYPE_CHECKING:
    from postal_inspector.config import Settings

logger = structlog.get_logger(__name__)


class BriefingScheduler:
    """Schedule daily briefing generation."""

    def __init__(self, settings: "Settings"):
        self.settings = settings
        self.generator = BriefingGenerator(settings)
        self.scheduler = AsyncIOScheduler()
        self._shutdown = asyncio.Event()

    async def run(self) -> None:
        """Start scheduler and run until shutdown."""
        logger.info(
            "scheduler_starting",
            briefing_hour=self.settings.briefing_hour,
            timezone=self.settings.tz,
        )

        # Schedule daily briefing
        self.scheduler.add_job(
            self._generate_and_deliver,
            trigger=CronTrigger(
                hour=self.settings.briefing_hour, minute=0, timezone=self.settings.tz
            ),
            id="daily_briefing",
            name="Daily Email Briefing",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("scheduler_running")

        # Wait for shutdown
        await self._shutdown.wait()

        self.scheduler.shutdown(wait=True)
        logger.info("scheduler_stopped")

    async def _generate_and_deliver(self) -> None:
        """Generate and deliver daily briefing."""
        logger.info("briefing_job_starting")

        try:
            html = await self.generator.generate()
            success = await self.generator.deliver_briefing(html)

            if success:
                logger.info("briefing_delivered")
            else:
                logger.error("briefing_delivery_failed")
        except Exception as e:
            logger.error("briefing_job_failed", error=str(e))

    async def generate_now(self) -> bool:
        """Generate and deliver briefing immediately."""
        logger.info("manual_briefing_triggered")
        await self._generate_and_deliver()
        return True

    def request_shutdown(self) -> None:
        """Signal graceful shutdown."""
        logger.info("scheduler_shutdown_requested")
        self._shutdown.set()
