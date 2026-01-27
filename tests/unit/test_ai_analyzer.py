"""Tests for AI analyzer with mocked Anthropic API."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from postal_inspector.models import ParsedEmail
from postal_inspector.scanner.ai_analyzer import AIAnalyzer
from postal_inspector.scanner.verdict import Verdict


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.anthropic_api_key.get_secret_value.return_value = "test-key"
    settings.anthropic_model = "claude-sonnet-4-20250514"
    settings.ai_timeout = 30.0
    settings.rate_limit_per_minute = 30
    return settings


@pytest.fixture
def sample_email():
    """Create a sample parsed email for testing."""
    return ParsedEmail(
        message_id="<test@example.com>",
        from_addr="sender@example.com",
        to_addr="recipient@example.com",
        reply_to=None,
        subject="Test email subject",
        body_preview="This is a test email body.",
        raw=b"From: sender@example.com\nSubject: Test\n\nBody",
    )


class TestResponseParsing:
    """Test AI response parsing logic."""

    def test_parse_safe_response(self, mock_settings: MagicMock) -> None:
        """Test parsing a SAFE verdict response."""
        with patch("postal_inspector.scanner.ai_analyzer.anthropic"):
            analyzer = AIAnalyzer(mock_settings)
            result = analyzer._parse_response("SAFE|Legitimate newsletter from known sender")

            assert result.verdict == Verdict.SAFE
            assert result.reason == "Legitimate newsletter from known sender"

    def test_parse_quarantine_response(self, mock_settings: MagicMock) -> None:
        """Test parsing a QUARANTINE verdict response."""
        with patch("postal_inspector.scanner.ai_analyzer.anthropic"):
            analyzer = AIAnalyzer(mock_settings)
            result = analyzer._parse_response("QUARANTINE|Typosquatting domain micros0ft.com")

            assert result.verdict == Verdict.QUARANTINE
            assert result.reason == "Typosquatting domain micros0ft.com"

    def test_parse_multiline_response(self, mock_settings: MagicMock) -> None:
        """Test parsing response with extra lines before verdict."""
        with patch("postal_inspector.scanner.ai_analyzer.anthropic"):
            analyzer = AIAnalyzer(mock_settings)
            response = """Let me analyze this email...

SAFE|Normal business correspondence

The email appears legitimate."""
            result = analyzer._parse_response(response)

            assert result.verdict == Verdict.SAFE
            assert result.reason == "Normal business correspondence"

    def test_invalid_response_fails_closed(self, mock_settings: MagicMock) -> None:
        """Test that invalid responses result in QUARANTINE (fail-closed)."""
        with patch("postal_inspector.scanner.ai_analyzer.anthropic"):
            analyzer = AIAnalyzer(mock_settings)
            result = analyzer._parse_response("This is not a valid verdict format")

            assert result.verdict == Verdict.QUARANTINE
            assert "Invalid AI response" in result.reason

    def test_empty_response_fails_closed(self, mock_settings: MagicMock) -> None:
        """Test that empty responses result in QUARANTINE (fail-closed)."""
        with patch("postal_inspector.scanner.ai_analyzer.anthropic"):
            analyzer = AIAnalyzer(mock_settings)
            result = analyzer._parse_response("")

            assert result.verdict == Verdict.QUARANTINE


class TestEmailAnalysis:
    """Test full email analysis flow with mocked API."""

    @pytest.mark.asyncio
    async def test_analyze_email_safe(
        self, mock_settings: MagicMock, sample_email: ParsedEmail
    ) -> None:
        """Test analyzing an email that gets SAFE verdict."""
        with patch("postal_inspector.scanner.ai_analyzer.anthropic") as mock_anthropic:
            # Mock the API response
            mock_response = MagicMock()
            mock_text_block = MagicMock()
            mock_text_block.text = "SAFE|Normal newsletter from linkedin.com"
            mock_response.content = [mock_text_block]

            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            # Need to patch TextBlock isinstance check
            with patch("postal_inspector.scanner.ai_analyzer.isinstance", return_value=True):
                analyzer = AIAnalyzer(mock_settings)
                # Clear rate limiter timestamps for test
                analyzer.rate_limiter.timestamps.clear()

                result = await analyzer.analyze_email(sample_email)

                assert result.verdict == Verdict.SAFE
                assert "linkedin" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_analyze_email_quarantine(
        self, mock_settings: MagicMock, sample_email: ParsedEmail
    ) -> None:
        """Test analyzing a suspicious email that gets QUARANTINE verdict."""
        with patch("postal_inspector.scanner.ai_analyzer.anthropic") as mock_anthropic:
            mock_response = MagicMock()
            mock_text_block = MagicMock()
            mock_text_block.text = "QUARANTINE|Urgency with credential request"
            mock_response.content = [mock_text_block]

            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            with patch("postal_inspector.scanner.ai_analyzer.isinstance", return_value=True):
                analyzer = AIAnalyzer(mock_settings)
                analyzer.rate_limiter.timestamps.clear()

                result = await analyzer.analyze_email(sample_email)

                assert result.verdict == Verdict.QUARANTINE
                assert "credential" in result.reason.lower()
