"""Tests for briefing scheduler module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from postal_inspector.services.scheduler import BriefingScheduler


class TestBriefingSchedulerInit:
    """Test BriefingScheduler initialization."""

    def test_scheduler_init(self) -> None:
        """Test BriefingScheduler initializes correctly."""
        mock_settings = MagicMock()
        mock_settings.briefing_hour = 8
        mock_settings.tz = "US/Central"
        mock_settings.anthropic_api_key.get_secret_value.return_value = "sk-test"

        with (
            patch("postal_inspector.services.scheduler.BriefingGenerator") as mock_gen_cls,
            patch("postal_inspector.services.scheduler.AsyncIOScheduler") as mock_sched_cls,
        ):
            scheduler = BriefingScheduler(mock_settings)

            assert scheduler.settings is mock_settings
            mock_gen_cls.assert_called_once_with(mock_settings)
            mock_sched_cls.assert_called_once()
            assert isinstance(scheduler._shutdown, asyncio.Event)

    def test_scheduler_creates_generator(self) -> None:
        """Test scheduler creates BriefingGenerator with settings."""
        mock_settings = MagicMock()
        mock_settings.briefing_hour = 10
        mock_settings.tz = "UTC"

        with (
            patch("postal_inspector.services.scheduler.BriefingGenerator") as mock_gen_cls,
            patch("postal_inspector.services.scheduler.AsyncIOScheduler"),
        ):
            mock_generator = MagicMock()
            mock_gen_cls.return_value = mock_generator

            scheduler = BriefingScheduler(mock_settings)

            assert scheduler.generator is mock_generator


class TestBriefingSchedulerRun:
    """Test BriefingScheduler.run() method."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.briefing_hour = 8
        settings.tz = "US/Central"
        settings.anthropic_api_key.get_secret_value.return_value = "sk-test"
        return settings

    @pytest.mark.asyncio
    async def test_run_starts_scheduler(self, mock_settings: MagicMock) -> None:
        """Test run() starts the APScheduler."""
        with (
            patch("postal_inspector.services.scheduler.BriefingGenerator"),
            patch("postal_inspector.services.scheduler.AsyncIOScheduler") as mock_sched_cls,
            patch("postal_inspector.services.scheduler.CronTrigger"),
        ):
            mock_scheduler = MagicMock()
            mock_sched_cls.return_value = mock_scheduler

            scheduler = BriefingScheduler(mock_settings)

            # Schedule shutdown immediately so run() doesn't block
            async def trigger_shutdown():
                await asyncio.sleep(0.01)
                scheduler.request_shutdown()

            # Run both coroutines concurrently
            await asyncio.gather(scheduler.run(), trigger_shutdown())

            mock_scheduler.start.assert_called_once()
            mock_scheduler.shutdown.assert_called_once_with(wait=True)

    @pytest.mark.asyncio
    async def test_run_adds_cron_job(self, mock_settings: MagicMock) -> None:
        """Test run() adds a cron job for daily briefing."""
        with (
            patch("postal_inspector.services.scheduler.BriefingGenerator"),
            patch("postal_inspector.services.scheduler.AsyncIOScheduler") as mock_sched_cls,
            patch("postal_inspector.services.scheduler.CronTrigger") as mock_trigger_cls,
        ):
            mock_scheduler = MagicMock()
            mock_sched_cls.return_value = mock_scheduler
            mock_trigger = MagicMock()
            mock_trigger_cls.return_value = mock_trigger

            scheduler = BriefingScheduler(mock_settings)

            async def trigger_shutdown():
                await asyncio.sleep(0.01)
                scheduler.request_shutdown()

            await asyncio.gather(scheduler.run(), trigger_shutdown())

            # Verify CronTrigger was created with correct parameters
            mock_trigger_cls.assert_called_once_with(
                hour=mock_settings.briefing_hour,
                minute=0,
                timezone=mock_settings.tz,
            )

            # Verify job was added
            mock_scheduler.add_job.assert_called_once()
            call_kwargs = mock_scheduler.add_job.call_args[1]
            assert call_kwargs["trigger"] is mock_trigger
            assert call_kwargs["id"] == "daily_briefing"
            assert call_kwargs["name"] == "Daily Email Briefing"
            assert call_kwargs["replace_existing"] is True


class TestBriefingSchedulerGenerateAndDeliver:
    """Test BriefingScheduler._generate_and_deliver() method."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.briefing_hour = 8
        settings.tz = "US/Central"
        return settings

    @pytest.mark.asyncio
    async def test_generate_and_deliver_success(self, mock_settings: MagicMock) -> None:
        """Test successful briefing generation and delivery."""
        with (
            patch("postal_inspector.services.scheduler.BriefingGenerator") as mock_gen_cls,
            patch("postal_inspector.services.scheduler.AsyncIOScheduler"),
        ):
            mock_generator = AsyncMock()
            mock_generator.generate = AsyncMock(return_value="<html>Briefing</html>")
            mock_generator.deliver_briefing = AsyncMock(return_value=True)
            mock_gen_cls.return_value = mock_generator

            scheduler = BriefingScheduler(mock_settings)
            await scheduler._generate_and_deliver()

            mock_generator.generate.assert_called_once()
            mock_generator.deliver_briefing.assert_called_once_with("<html>Briefing</html>")

    @pytest.mark.asyncio
    async def test_generate_and_deliver_delivery_failed(self, mock_settings: MagicMock) -> None:
        """Test briefing delivery failure is logged but doesn't raise."""
        with (
            patch("postal_inspector.services.scheduler.BriefingGenerator") as mock_gen_cls,
            patch("postal_inspector.services.scheduler.AsyncIOScheduler"),
        ):
            mock_generator = AsyncMock()
            mock_generator.generate = AsyncMock(return_value="<html>Briefing</html>")
            mock_generator.deliver_briefing = AsyncMock(return_value=False)
            mock_gen_cls.return_value = mock_generator

            scheduler = BriefingScheduler(mock_settings)

            # Should not raise even though delivery failed
            await scheduler._generate_and_deliver()

            mock_generator.generate.assert_called_once()
            mock_generator.deliver_briefing.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_and_deliver_exception_handled(self, mock_settings: MagicMock) -> None:
        """Test exception during generation is caught and logged."""
        with (
            patch("postal_inspector.services.scheduler.BriefingGenerator") as mock_gen_cls,
            patch("postal_inspector.services.scheduler.AsyncIOScheduler"),
        ):
            mock_generator = AsyncMock()
            mock_generator.generate = AsyncMock(side_effect=Exception("AI service unavailable"))
            mock_gen_cls.return_value = mock_generator

            scheduler = BriefingScheduler(mock_settings)

            # Should not raise, exception is caught
            await scheduler._generate_and_deliver()

            mock_generator.generate.assert_called_once()
            # deliver_briefing should not be called since generate failed
            mock_generator.deliver_briefing.assert_not_called()


class TestBriefingSchedulerGenerateNow:
    """Test BriefingScheduler.generate_now() method."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.briefing_hour = 8
        settings.tz = "US/Central"
        return settings

    @pytest.mark.asyncio
    async def test_generate_now_calls_generate_and_deliver(self, mock_settings: MagicMock) -> None:
        """Test generate_now() calls _generate_and_deliver()."""
        with (
            patch("postal_inspector.services.scheduler.BriefingGenerator") as mock_gen_cls,
            patch("postal_inspector.services.scheduler.AsyncIOScheduler"),
        ):
            mock_generator = AsyncMock()
            mock_generator.generate = AsyncMock(return_value="<html>Now</html>")
            mock_generator.deliver_briefing = AsyncMock(return_value=True)
            mock_gen_cls.return_value = mock_generator

            scheduler = BriefingScheduler(mock_settings)
            result = await scheduler.generate_now()

            assert result is True
            mock_generator.generate.assert_called_once()
            mock_generator.deliver_briefing.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_now_returns_true_even_on_failure(
        self, mock_settings: MagicMock
    ) -> None:
        """Test generate_now() returns True even if delivery fails."""
        with (
            patch("postal_inspector.services.scheduler.BriefingGenerator") as mock_gen_cls,
            patch("postal_inspector.services.scheduler.AsyncIOScheduler"),
        ):
            mock_generator = AsyncMock()
            mock_generator.generate = AsyncMock(return_value="<html>Failed</html>")
            mock_generator.deliver_briefing = AsyncMock(return_value=False)
            mock_gen_cls.return_value = mock_generator

            scheduler = BriefingScheduler(mock_settings)
            result = await scheduler.generate_now()

            # generate_now always returns True as per current implementation
            assert result is True


class TestBriefingSchedulerRequestShutdown:
    """Test BriefingScheduler.request_shutdown() method."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.briefing_hour = 8
        settings.tz = "US/Central"
        return settings

    def test_request_shutdown_sets_event(self, mock_settings: MagicMock) -> None:
        """Test request_shutdown() sets the shutdown event."""
        with (
            patch("postal_inspector.services.scheduler.BriefingGenerator"),
            patch("postal_inspector.services.scheduler.AsyncIOScheduler"),
        ):
            scheduler = BriefingScheduler(mock_settings)

            assert not scheduler._shutdown.is_set()
            scheduler.request_shutdown()
            assert scheduler._shutdown.is_set()

    @pytest.mark.asyncio
    async def test_request_shutdown_unblocks_run(self, mock_settings: MagicMock) -> None:
        """Test request_shutdown() unblocks the run() method."""
        with (
            patch("postal_inspector.services.scheduler.BriefingGenerator"),
            patch("postal_inspector.services.scheduler.AsyncIOScheduler") as mock_sched_cls,
            patch("postal_inspector.services.scheduler.CronTrigger"),
        ):
            mock_scheduler = MagicMock()
            mock_sched_cls.return_value = mock_scheduler

            scheduler = BriefingScheduler(mock_settings)

            async def delayed_shutdown():
                await asyncio.sleep(0.01)
                scheduler.request_shutdown()

            # run() should complete after shutdown is requested
            await asyncio.gather(scheduler.run(), delayed_shutdown())

            # Verify shutdown was called
            mock_scheduler.shutdown.assert_called_once_with(wait=True)


class TestBriefingSchedulerIntegration:
    """Integration tests for BriefingScheduler."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.briefing_hour = 9
        settings.tz = "America/New_York"
        return settings

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, mock_settings: MagicMock) -> None:
        """Test full scheduler lifecycle: init, run, shutdown."""
        with (
            patch("postal_inspector.services.scheduler.BriefingGenerator") as mock_gen_cls,
            patch("postal_inspector.services.scheduler.AsyncIOScheduler") as mock_sched_cls,
        ):
            mock_generator = AsyncMock()
            mock_gen_cls.return_value = mock_generator
            mock_scheduler_instance = MagicMock()
            mock_sched_cls.return_value = mock_scheduler_instance

            scheduler = BriefingScheduler(mock_settings)

            async def lifecycle():
                # Simulate short run then shutdown
                await asyncio.sleep(0.01)
                scheduler.request_shutdown()

            await asyncio.gather(scheduler.run(), lifecycle())

            # Verify scheduler was properly started and stopped
            mock_scheduler_instance.start.assert_called_once()
            mock_scheduler_instance.shutdown.assert_called_once_with(wait=True)

    @pytest.mark.asyncio
    async def test_multiple_generate_now_calls(self, mock_settings: MagicMock) -> None:
        """Test multiple generate_now() calls work correctly."""
        with (
            patch("postal_inspector.services.scheduler.BriefingGenerator") as mock_gen_cls,
            patch("postal_inspector.services.scheduler.AsyncIOScheduler"),
        ):
            mock_generator = AsyncMock()
            mock_generator.generate = AsyncMock(return_value="<html>Briefing</html>")
            mock_generator.deliver_briefing = AsyncMock(return_value=True)
            mock_gen_cls.return_value = mock_generator

            scheduler = BriefingScheduler(mock_settings)

            # Call generate_now multiple times
            result1 = await scheduler.generate_now()
            result2 = await scheduler.generate_now()
            result3 = await scheduler.generate_now()

            assert result1 is True
            assert result2 is True
            assert result3 is True
            assert mock_generator.generate.call_count == 3
            assert mock_generator.deliver_briefing.call_count == 3


class TestBriefingSchedulerSettingsUsage:
    """Test that scheduler correctly uses settings values."""

    @pytest.mark.asyncio
    async def test_uses_briefing_hour_from_settings(self) -> None:
        """Test scheduler uses briefing_hour from settings."""
        mock_settings = MagicMock()
        mock_settings.briefing_hour = 14  # 2 PM
        mock_settings.tz = "Europe/London"

        with (
            patch("postal_inspector.services.scheduler.BriefingGenerator"),
            patch("postal_inspector.services.scheduler.AsyncIOScheduler") as mock_sched_cls,
            patch("postal_inspector.services.scheduler.CronTrigger") as mock_trigger_cls,
        ):
            mock_scheduler = MagicMock()
            mock_sched_cls.return_value = mock_scheduler

            scheduler = BriefingScheduler(mock_settings)

            async def trigger_shutdown():
                await asyncio.sleep(0.01)
                scheduler.request_shutdown()

            await asyncio.gather(scheduler.run(), trigger_shutdown())

            # Verify the hour and timezone were passed correctly
            mock_trigger_cls.assert_called_once_with(hour=14, minute=0, timezone="Europe/London")

    @pytest.mark.asyncio
    async def test_uses_different_timezones(self) -> None:
        """Test scheduler handles different timezone settings."""
        for tz in ["US/Pacific", "US/Eastern", "UTC", "Asia/Tokyo"]:
            mock_settings = MagicMock()
            mock_settings.briefing_hour = 8
            mock_settings.tz = tz

            with (
                patch("postal_inspector.services.scheduler.BriefingGenerator"),
                patch("postal_inspector.services.scheduler.AsyncIOScheduler") as mock_sched_cls,
                patch("postal_inspector.services.scheduler.CronTrigger") as mock_trigger_cls,
            ):
                mock_scheduler = MagicMock()
                mock_sched_cls.return_value = mock_scheduler

                sched = BriefingScheduler(mock_settings)

                async def trigger_shutdown(s=sched):
                    await asyncio.sleep(0.01)
                    s.request_shutdown()

                await asyncio.gather(sched.run(), trigger_shutdown())

                call_args = mock_trigger_cls.call_args[1]
                assert call_args["timezone"] == tz
