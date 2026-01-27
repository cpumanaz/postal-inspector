"""Command-line interface for Postal Inspector."""

import asyncio
import contextlib
import signal
import sys
from types import FrameType

import click
import structlog

from postal_inspector.briefing import HealthChecker
from postal_inspector.briefing.health import HealthReport
from postal_inspector.config import get_settings
from postal_inspector.core import configure_logging
from postal_inspector.services import BriefingScheduler, MailProcessor

logger = structlog.get_logger(__name__)


@click.group()
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
@click.option("--json-logs/--no-json-logs", default=False, help="JSON log format")
@click.pass_context
def main(ctx: click.Context, debug: bool, json_logs: bool) -> None:
    """Postal Inspector - AI-powered email security scanner."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    ctx.obj["json_logs"] = json_logs
    configure_logging(json_format=json_logs, debug=debug)


@main.command()
@click.pass_context
def scanner(ctx: click.Context) -> None:
    """Run the mail processor service."""
    logger.info("starting_scanner_service")

    try:
        settings = get_settings()
    except Exception as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)

    processor = MailProcessor(settings)

    # Handle signals
    def handle_signal(signum: int, frame: FrameType | None) -> None:
        logger.info("signal_received", signal=signum)
        processor.request_shutdown()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        asyncio.run(processor.run())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error("scanner_crashed", error=str(e))
        sys.exit(1)


@main.command()
@click.option("--now", is_flag=True, help="Generate briefing immediately")
@click.option("--schedule", is_flag=True, help="Run scheduler service")
@click.pass_context
def briefing(ctx: click.Context, now: bool, schedule: bool) -> None:
    """Generate or schedule daily briefings."""
    try:
        settings = get_settings()
    except Exception as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)

    scheduler = BriefingScheduler(settings)

    if now:
        logger.info("generating_immediate_briefing")
        asyncio.run(scheduler.generate_now())
        click.echo("Briefing generated and delivered.")
    elif schedule:
        logger.info("starting_scheduler_service")

        def handle_signal(signum: int, frame: FrameType | None) -> None:
            scheduler.request_shutdown()

        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)

        with contextlib.suppress(KeyboardInterrupt):
            asyncio.run(scheduler.run())
    else:
        click.echo("Use --now for immediate briefing or --schedule to run scheduler.")
        sys.exit(1)


@main.command()
@click.pass_context
def health(ctx: click.Context) -> None:
    """Run system health checks."""
    try:
        settings = get_settings()
    except Exception as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)

    async def run_checks() -> HealthReport:
        checker = HealthChecker(settings)
        report = await checker.check_all()
        return report

    report = asyncio.run(run_checks())

    # Output status
    status_icon = {"healthy": "✅", "warning": "⚠️", "critical": "❌"}

    click.echo(
        f"\n{status_icon.get(report.status.value, '?')} Status: {report.status.value.upper()}"
    )
    click.echo(f"   Staging queue: {report.staging_count}")
    click.echo(f"   Failed emails: {report.failed_count}")
    click.echo(f"   LMTP available: {'Yes' if report.lmtp_available else 'No'}")

    if report.issues:
        click.echo("\nIssues:")
        for issue in report.issues:
            # Strip HTML tags for CLI
            clean = issue.replace("<strong>", "").replace("</strong>", "")
            click.echo(f"   ❌ {clean}")

    if report.warnings:
        click.echo("\nWarnings:")
        for warning in report.warnings:
            click.echo(f"   ⚠️  {warning}")

    # Exit code based on status
    if report.status.value == "critical":
        sys.exit(2)
    elif report.status.value == "warning":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
