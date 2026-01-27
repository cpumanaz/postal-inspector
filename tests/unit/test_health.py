"""Tests for health check module."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from postal_inspector.briefing.health import (
    HealthChecker,
    HealthReport,
    HealthStatus,
)


class TestHealthStatus:
    """Test HealthStatus enum."""

    def test_health_status_values(self) -> None:
        """Test HealthStatus enum values."""
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.WARNING == "warning"
        assert HealthStatus.CRITICAL == "critical"

    def test_health_status_is_string_enum(self) -> None:
        """Test HealthStatus inherits from str."""
        assert isinstance(HealthStatus.HEALTHY, str)
        assert isinstance(HealthStatus.WARNING, str)
        assert isinstance(HealthStatus.CRITICAL, str)


class TestHealthReport:
    """Test HealthReport dataclass."""

    def test_health_report_defaults(self) -> None:
        """Test HealthReport default values."""
        report = HealthReport(status=HealthStatus.HEALTHY)
        assert report.status == HealthStatus.HEALTHY
        assert report.issues == []
        assert report.warnings == []
        assert report.staging_count == 0
        assert report.failed_count == 0
        assert report.lmtp_available is True
        assert isinstance(report.checked_at, datetime)

    def test_health_report_with_issues(self) -> None:
        """Test HealthReport with issues and warnings."""
        report = HealthReport(
            status=HealthStatus.CRITICAL,
            issues=["LMTP down", "Failed emails"],
            warnings=["High staging count"],
            staging_count=15,
            failed_count=3,
            lmtp_available=False,
        )
        assert report.status == HealthStatus.CRITICAL
        assert len(report.issues) == 2
        assert len(report.warnings) == 1
        assert report.staging_count == 15
        assert report.failed_count == 3
        assert report.lmtp_available is False


class TestHealthReportToHtml:
    """Test HealthReport.to_html() method."""

    def test_healthy_report_html(self) -> None:
        """Test HTML generation for healthy status."""
        report = HealthReport(status=HealthStatus.HEALTHY)
        html = report.to_html()

        assert "All systems operational" in html
        assert "#d4edda" in html  # Green background
        assert "#155724" in html  # Green text color
        assert "&#10004;" in html  # Checkmark

    def test_warning_report_html(self) -> None:
        """Test HTML generation for warning status."""
        report = HealthReport(
            status=HealthStatus.WARNING,
            warnings=["15 emails in staging queue"],
        )
        html = report.to_html()

        assert "System Notice" in html
        assert "#fff3cd" in html  # Yellow background
        assert "#856404" in html  # Yellow/brown text color
        assert "#ffc107" in html  # Yellow border
        assert "15 emails in staging queue" in html
        assert "&#9889;" in html  # Lightning bolt icon

    def test_critical_report_html(self) -> None:
        """Test HTML generation for critical status."""
        report = HealthReport(
            status=HealthStatus.CRITICAL,
            issues=["LMTP service unreachable!", "5 emails failed delivery"],
        )
        html = report.to_html()

        assert "System Alert" in html
        assert "#f8d7da" in html  # Red background
        assert "#721c24" in html  # Red text color
        assert "#f5c6cb" in html  # Red border
        assert "LMTP service unreachable!" in html
        assert "5 emails failed delivery" in html
        assert "&#9888;" in html  # Warning icon

    def test_critical_report_combines_issues_and_warnings(self) -> None:
        """Test that critical report shows both issues and warnings."""
        report = HealthReport(
            status=HealthStatus.CRITICAL,
            issues=["Critical issue"],
            warnings=["Warning message"],
        )
        html = report.to_html()

        assert "Critical issue" in html
        assert "Warning message" in html

    def test_html_contains_list_items(self) -> None:
        """Test HTML contains proper list items."""
        report = HealthReport(
            status=HealthStatus.WARNING,
            warnings=["First warning", "Second warning"],
        )
        html = report.to_html()

        assert "<li>First warning</li>" in html
        assert "<li>Second warning</li>" in html
        assert "<ul" in html


class TestHealthChecker:
    """Test HealthChecker class."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.maildir_path = "/var/mail"
        settings.mail_user = "testuser"
        settings.lmtp_host = "localhost"
        settings.lmtp_port = 24
        return settings

    @pytest.fixture
    def mock_maildir(self) -> AsyncMock:
        """Create mock MaildirManager."""
        maildir = AsyncMock()
        maildir.count_staging = AsyncMock(return_value=0)
        maildir.count_failed = AsyncMock(return_value=0)
        return maildir

    @pytest.fixture
    def mock_lmtp(self) -> AsyncMock:
        """Create mock LMTPDelivery."""
        lmtp = AsyncMock()
        lmtp.check_connection = AsyncMock(return_value=True)
        return lmtp

    @pytest.mark.asyncio
    async def test_check_all_healthy(
        self, mock_settings: MagicMock, mock_maildir: AsyncMock, mock_lmtp: AsyncMock
    ) -> None:
        """Test health check returns HEALTHY when all checks pass."""
        with (
            patch(
                "postal_inspector.briefing.health.MaildirManager",
                return_value=mock_maildir,
            ),
            patch("postal_inspector.briefing.health.LMTPDelivery", return_value=mock_lmtp),
        ):
            checker = HealthChecker(mock_settings)
            report = await checker.check_all()

            assert report.status == HealthStatus.HEALTHY
            assert report.issues == []
            assert report.warnings == []
            assert report.staging_count == 0
            assert report.failed_count == 0
            assert report.lmtp_available is True

    @pytest.mark.asyncio
    async def test_check_all_warning_staging(
        self, mock_settings: MagicMock, mock_maildir: AsyncMock, mock_lmtp: AsyncMock
    ) -> None:
        """Test health check returns WARNING when staging count is 11-50."""
        mock_maildir.count_staging = AsyncMock(return_value=15)

        with (
            patch(
                "postal_inspector.briefing.health.MaildirManager",
                return_value=mock_maildir,
            ),
            patch("postal_inspector.briefing.health.LMTPDelivery", return_value=mock_lmtp),
        ):
            checker = HealthChecker(mock_settings)
            report = await checker.check_all()

            assert report.status == HealthStatus.WARNING
            assert len(report.warnings) == 1
            assert "15 emails in staging queue" in report.warnings[0]
            assert report.staging_count == 15

    @pytest.mark.asyncio
    async def test_check_all_critical_high_staging(
        self, mock_settings: MagicMock, mock_maildir: AsyncMock, mock_lmtp: AsyncMock
    ) -> None:
        """Test health check returns CRITICAL when staging count > 50."""
        mock_maildir.count_staging = AsyncMock(return_value=75)

        with (
            patch(
                "postal_inspector.briefing.health.MaildirManager",
                return_value=mock_maildir,
            ),
            patch("postal_inspector.briefing.health.LMTPDelivery", return_value=mock_lmtp),
        ):
            checker = HealthChecker(mock_settings)
            report = await checker.check_all()

            assert report.status == HealthStatus.CRITICAL
            assert len(report.issues) == 1
            assert "75 emails stuck in staging" in report.issues[0]
            assert report.staging_count == 75

    @pytest.mark.asyncio
    async def test_check_all_critical_failed_emails(
        self, mock_settings: MagicMock, mock_maildir: AsyncMock, mock_lmtp: AsyncMock
    ) -> None:
        """Test health check returns CRITICAL when failed emails exist."""
        mock_maildir.count_failed = AsyncMock(return_value=3)

        with (
            patch(
                "postal_inspector.briefing.health.MaildirManager",
                return_value=mock_maildir,
            ),
            patch("postal_inspector.briefing.health.LMTPDelivery", return_value=mock_lmtp),
        ):
            checker = HealthChecker(mock_settings)
            report = await checker.check_all()

            assert report.status == HealthStatus.CRITICAL
            assert len(report.issues) == 1
            assert "3 emails failed delivery" in report.issues[0]
            assert report.failed_count == 3

    @pytest.mark.asyncio
    async def test_check_all_critical_lmtp_down(
        self, mock_settings: MagicMock, mock_maildir: AsyncMock, mock_lmtp: AsyncMock
    ) -> None:
        """Test health check returns CRITICAL when LMTP is unreachable."""
        mock_lmtp.check_connection = AsyncMock(return_value=False)

        with (
            patch(
                "postal_inspector.briefing.health.MaildirManager",
                return_value=mock_maildir,
            ),
            patch("postal_inspector.briefing.health.LMTPDelivery", return_value=mock_lmtp),
        ):
            checker = HealthChecker(mock_settings)
            report = await checker.check_all()

            assert report.status == HealthStatus.CRITICAL
            assert len(report.issues) == 1
            assert "LMTP service unreachable" in report.issues[0]
            assert report.lmtp_available is False

    @pytest.mark.asyncio
    async def test_check_all_multiple_issues(
        self, mock_settings: MagicMock, mock_maildir: AsyncMock, mock_lmtp: AsyncMock
    ) -> None:
        """Test health check with multiple critical issues."""
        mock_maildir.count_staging = AsyncMock(return_value=100)
        mock_maildir.count_failed = AsyncMock(return_value=5)
        mock_lmtp.check_connection = AsyncMock(return_value=False)

        with (
            patch(
                "postal_inspector.briefing.health.MaildirManager",
                return_value=mock_maildir,
            ),
            patch("postal_inspector.briefing.health.LMTPDelivery", return_value=mock_lmtp),
        ):
            checker = HealthChecker(mock_settings)
            report = await checker.check_all()

            assert report.status == HealthStatus.CRITICAL
            assert len(report.issues) == 3
            assert report.staging_count == 100
            assert report.failed_count == 5
            assert report.lmtp_available is False

    @pytest.mark.asyncio
    async def test_check_all_staging_boundary_10(
        self, mock_settings: MagicMock, mock_maildir: AsyncMock, mock_lmtp: AsyncMock
    ) -> None:
        """Test staging count at boundary (10) - should be healthy."""
        mock_maildir.count_staging = AsyncMock(return_value=10)

        with (
            patch(
                "postal_inspector.briefing.health.MaildirManager",
                return_value=mock_maildir,
            ),
            patch("postal_inspector.briefing.health.LMTPDelivery", return_value=mock_lmtp),
        ):
            checker = HealthChecker(mock_settings)
            report = await checker.check_all()

            assert report.status == HealthStatus.HEALTHY
            assert report.staging_count == 10

    @pytest.mark.asyncio
    async def test_check_all_staging_boundary_11(
        self, mock_settings: MagicMock, mock_maildir: AsyncMock, mock_lmtp: AsyncMock
    ) -> None:
        """Test staging count at boundary (11) - should be warning."""
        mock_maildir.count_staging = AsyncMock(return_value=11)

        with (
            patch(
                "postal_inspector.briefing.health.MaildirManager",
                return_value=mock_maildir,
            ),
            patch("postal_inspector.briefing.health.LMTPDelivery", return_value=mock_lmtp),
        ):
            checker = HealthChecker(mock_settings)
            report = await checker.check_all()

            assert report.status == HealthStatus.WARNING
            assert report.staging_count == 11

    @pytest.mark.asyncio
    async def test_check_all_staging_boundary_50(
        self, mock_settings: MagicMock, mock_maildir: AsyncMock, mock_lmtp: AsyncMock
    ) -> None:
        """Test staging count at boundary (50) - should be warning."""
        mock_maildir.count_staging = AsyncMock(return_value=50)

        with (
            patch(
                "postal_inspector.briefing.health.MaildirManager",
                return_value=mock_maildir,
            ),
            patch("postal_inspector.briefing.health.LMTPDelivery", return_value=mock_lmtp),
        ):
            checker = HealthChecker(mock_settings)
            report = await checker.check_all()

            assert report.status == HealthStatus.WARNING
            assert report.staging_count == 50

    @pytest.mark.asyncio
    async def test_check_all_staging_boundary_51(
        self, mock_settings: MagicMock, mock_maildir: AsyncMock, mock_lmtp: AsyncMock
    ) -> None:
        """Test staging count at boundary (51) - should be critical."""
        mock_maildir.count_staging = AsyncMock(return_value=51)

        with (
            patch(
                "postal_inspector.briefing.health.MaildirManager",
                return_value=mock_maildir,
            ),
            patch("postal_inspector.briefing.health.LMTPDelivery", return_value=mock_lmtp),
        ):
            checker = HealthChecker(mock_settings)
            report = await checker.check_all()

            assert report.status == HealthStatus.CRITICAL
            assert report.staging_count == 51

    @pytest.mark.asyncio
    async def test_check_all_warning_not_elevated_when_critical(
        self, mock_settings: MagicMock, mock_maildir: AsyncMock, mock_lmtp: AsyncMock
    ) -> None:
        """Test warning doesn't override existing critical status."""
        # High staging (warning level) + failed emails (critical)
        mock_maildir.count_staging = AsyncMock(return_value=20)
        mock_maildir.count_failed = AsyncMock(return_value=1)

        with (
            patch(
                "postal_inspector.briefing.health.MaildirManager",
                return_value=mock_maildir,
            ),
            patch("postal_inspector.briefing.health.LMTPDelivery", return_value=mock_lmtp),
        ):
            checker = HealthChecker(mock_settings)
            report = await checker.check_all()

            # Status should be CRITICAL due to failed emails
            assert report.status == HealthStatus.CRITICAL
            # But we should still have the warning
            assert len(report.warnings) == 1
            assert "20 emails" in report.warnings[0]


class TestHealthCheckerInit:
    """Test HealthChecker initialization."""

    def test_health_checker_creates_dependencies(self) -> None:
        """Test HealthChecker creates MaildirManager and LMTPDelivery."""
        mock_settings = MagicMock()
        mock_settings.maildir_path = "/var/mail"
        mock_settings.mail_user = "testuser"
        mock_settings.lmtp_host = "localhost"
        mock_settings.lmtp_port = 24

        with (
            patch("postal_inspector.briefing.health.MaildirManager") as mock_maildir_cls,
            patch("postal_inspector.briefing.health.LMTPDelivery") as mock_lmtp_cls,
        ):
            checker = HealthChecker(mock_settings)

            mock_maildir_cls.assert_called_once_with(mock_settings)
            mock_lmtp_cls.assert_called_once_with(mock_settings)
            assert checker.settings is mock_settings


class TestHealthReportCustomCheckedAt:
    """Test HealthReport with custom checked_at timestamp."""

    def test_custom_checked_at(self) -> None:
        """Test HealthReport with custom timestamp."""
        custom_time = datetime(2024, 1, 15, 10, 30, 0)
        report = HealthReport(status=HealthStatus.HEALTHY, checked_at=custom_time)
        assert report.checked_at == custom_time

    def test_default_checked_at_is_now(self) -> None:
        """Test HealthReport default timestamp is close to now."""
        before = datetime.now()
        report = HealthReport(status=HealthStatus.HEALTHY)
        after = datetime.now()

        assert before <= report.checked_at <= after
