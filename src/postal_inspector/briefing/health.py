"""System health monitoring."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

import structlog

from postal_inspector.transport.lmtp_client import LMTPDelivery
from postal_inspector.transport.maildir import MaildirManager

if TYPE_CHECKING:
    from postal_inspector.config import Settings

logger = structlog.get_logger(__name__)

# How long without a successful fetch before we consider it stale
FETCH_STALE_THRESHOLD = timedelta(hours=1)
FETCH_CRITICAL_THRESHOLD = timedelta(hours=6)


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class HealthReport:
    status: HealthStatus
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    staging_count: int = 0
    failed_count: int = 0
    lmtp_available: bool = True
    imap_connected: bool = True
    last_fetch: datetime | None = None
    imap_failures: int = 0
    checked_at: datetime = field(default_factory=datetime.now)

    def to_html(self) -> str:
        """Generate HTML health report section."""
        if self.status == HealthStatus.CRITICAL:
            bg_color = "#f8d7da"
            border_color = "#f5c6cb"
            text_color = "#721c24"
            icon = "&#9888;&#65039;"
            title = "System Alert"
        elif self.status == HealthStatus.WARNING:
            bg_color = "#fff3cd"
            border_color = "#ffc107"
            text_color = "#856404"
            icon = "&#9889;"
            title = "System Notice"
        else:
            return """<div style="background-color: #d4edda; border: 1px solid #c3e6cb;
                       border-radius: 8px; padding: 12px; margin-bottom: 20px; text-align: center;">
                       <span style="color: #155724;">&#10004;&#65039; All systems operational</span></div>"""

        items = "".join(f"<li>{issue}</li>" for issue in self.issues + self.warnings)
        return f"""<div style="background-color: {bg_color}; border: 1px solid {border_color};
                   border-radius: 8px; padding: 16px; margin-bottom: 20px;">
                   <h3 style="margin: 0 0 12px 0; color: {text_color};">{icon} {title}</h3>
                   <ul style="margin: 0; padding-left: 20px; color: {text_color};">{items}</ul></div>"""


class HealthChecker:
    """Check system health status."""

    def __init__(self, settings: "Settings"):
        self.settings = settings
        self.maildir = MaildirManager(settings)
        self.lmtp = LMTPDelivery(settings)

    async def check_all(self) -> HealthReport:
        """Run all health checks."""
        issues: list[str] = []
        warnings: list[str] = []
        status = HealthStatus.HEALTHY

        # Check 1: Staging queue
        staging_count = await self.maildir.count_staging()
        if staging_count > 50:
            status = HealthStatus.CRITICAL
            issues.append(
                f"<strong>{staging_count} emails stuck in staging!</strong> Mail delivery may be failing."
            )
        elif staging_count > 10:
            if status == HealthStatus.HEALTHY:
                status = HealthStatus.WARNING
            warnings.append(f"{staging_count} emails in staging queue")

        # Check 2: Failed emails
        failed_count = await self.maildir.count_failed()
        if failed_count > 0:
            status = HealthStatus.CRITICAL
            issues.append(
                f"<strong>{failed_count} emails failed delivery!</strong> Manual review required."
            )

        # Check 3: LMTP connectivity
        lmtp_ok = await self.lmtp.check_connection()
        if not lmtp_ok:
            status = HealthStatus.CRITICAL
            issues.append("<strong>LMTP service unreachable!</strong> Email delivery is broken.")

        # Check 4: Mail processor / IMAP status
        imap_connected = True
        last_fetch: datetime | None = None
        imap_failures = 0

        processor_status = await self.maildir.read_processor_status()
        if processor_status:
            imap_connected = processor_status.get("is_connected", True)
            imap_failures = processor_status.get("consecutive_failures", 0)
            last_fetch_str = processor_status.get("last_successful_fetch")
            if last_fetch_str:
                try:
                    last_fetch = datetime.fromisoformat(last_fetch_str)
                except ValueError:
                    pass

            # Check if IMAP is disconnected
            if not imap_connected:
                status = HealthStatus.CRITICAL
                last_error = processor_status.get("last_error", "Unknown error")
                issues.append(
                    f"<strong>Mail fetcher disconnected from Migadu!</strong> Error: {last_error[:100]}"
                )

            # Check for consecutive failures
            elif imap_failures >= 3:
                status = HealthStatus.CRITICAL
                issues.append(
                    f"<strong>Mail fetcher has {imap_failures} consecutive failures!</strong> "
                    "Check upstream IMAP connectivity."
                )

            # Check if last fetch is stale
            if last_fetch:
                time_since_fetch = datetime.now() - last_fetch
                if time_since_fetch > FETCH_CRITICAL_THRESHOLD:
                    status = HealthStatus.CRITICAL
                    hours = int(time_since_fetch.total_seconds() / 3600)
                    issues.append(
                        f"<strong>No emails fetched in {hours} hours!</strong> "
                        "Mail processor may be stuck."
                    )
                elif time_since_fetch > FETCH_STALE_THRESHOLD:
                    if status == HealthStatus.HEALTHY:
                        status = HealthStatus.WARNING
                    minutes = int(time_since_fetch.total_seconds() / 60)
                    warnings.append(f"Last email fetch was {minutes} minutes ago")

        logger.info(
            "health_check_complete",
            status=status.value,
            staging=staging_count,
            failed=failed_count,
            lmtp_ok=lmtp_ok,
            imap_connected=imap_connected,
            imap_failures=imap_failures,
        )

        return HealthReport(
            status=status,
            issues=issues,
            warnings=warnings,
            staging_count=staging_count,
            failed_count=failed_count,
            lmtp_available=lmtp_ok,
            imap_connected=imap_connected,
            last_fetch=last_fetch,
            imap_failures=imap_failures,
        )
