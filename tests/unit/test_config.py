"""Tests for configuration settings module."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from postal_inspector.config.settings import Settings, get_settings


# Helper function to create Settings without loading .env file
def create_settings(**kwargs) -> Settings:
    """Create Settings instance without loading .env file."""
    return Settings(_env_file=None, **kwargs)


class TestSettingsValidation:
    """Test Pydantic validation for Settings class."""

    def test_valid_settings_minimal(self) -> None:
        """Test creating settings with required fields only."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret123",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass123",
            anthropic_api_key="sk-ant-test-key",
        )
        assert settings.mail_user == "testuser"
        assert settings.mail_pass.get_secret_value() == "secret123"
        assert settings.mail_domain == "example.com"
        assert settings.upstream_server == "imap.example.com"

    def test_default_values_applied(self) -> None:
        """Test that default values are applied correctly."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret123",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass123",
            anthropic_api_key="sk-ant-test-key",
        )
        # Check defaults
        assert settings.upstream_port == 993
        assert settings.fetch_interval == 300
        assert settings.rate_limit_per_minute == 30
        assert settings.max_retries == 5
        assert settings.lmtp_host == "imap"
        assert settings.lmtp_port == 24
        assert settings.anthropic_model == "claude-sonnet-4-20250514"
        assert settings.ai_timeout == 45
        assert settings.briefing_hour == 8
        assert settings.maildir_path == "/var/mail"
        assert settings.log_path == "/app/logs"
        assert settings.tz == "US/Central"
        assert settings.log_format == "console"
        assert settings.debug is False


class TestMailUserValidation:
    """Test mail_user field validation pattern: ^[a-zA-Z0-9_-]+$"""

    def test_valid_mail_user_alphanumeric(self) -> None:
        """Test valid alphanumeric mail user."""
        settings = create_settings(
            mail_user="testuser123",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
        )
        assert settings.mail_user == "testuser123"

    def test_valid_mail_user_with_underscore(self) -> None:
        """Test valid mail user with underscore."""
        settings = create_settings(
            mail_user="test_user",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
        )
        assert settings.mail_user == "test_user"

    def test_valid_mail_user_with_hyphen(self) -> None:
        """Test valid mail user with hyphen."""
        settings = create_settings(
            mail_user="test-user",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
        )
        assert settings.mail_user == "test-user"

    def test_invalid_mail_user_with_space(self) -> None:
        """Test invalid mail user containing space."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="test user",
                mail_pass="secret",
                mail_domain="example.com",
                upstream_server="imap.example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
            )
        assert "mail_user" in str(exc_info.value)

    def test_invalid_mail_user_with_at_symbol(self) -> None:
        """Test invalid mail user containing @ symbol."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="user@domain",
                mail_pass="secret",
                mail_domain="example.com",
                upstream_server="imap.example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
            )
        assert "mail_user" in str(exc_info.value)

    def test_invalid_mail_user_with_dot(self) -> None:
        """Test invalid mail user containing dot."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="user.name",
                mail_pass="secret",
                mail_domain="example.com",
                upstream_server="imap.example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
            )
        assert "mail_user" in str(exc_info.value)

    def test_invalid_mail_user_empty(self) -> None:
        """Test invalid empty mail user."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="",
                mail_pass="secret",
                mail_domain="example.com",
                upstream_server="imap.example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
            )
        assert "mail_user" in str(exc_info.value)


class TestMailDomainValidation:
    """Test mail_domain field validation pattern: ^[a-zA-Z0-9.-]+$"""

    def test_valid_domain_simple(self) -> None:
        """Test valid simple domain."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
        )
        assert settings.mail_domain == "example.com"

    def test_valid_domain_subdomain(self) -> None:
        """Test valid domain with subdomain."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="mail.example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
        )
        assert settings.mail_domain == "mail.example.com"

    def test_valid_domain_with_hyphen(self) -> None:
        """Test valid domain with hyphen."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="my-domain.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
        )
        assert settings.mail_domain == "my-domain.com"

    def test_invalid_domain_with_underscore(self) -> None:
        """Test invalid domain containing underscore."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="testuser",
                mail_pass="secret",
                mail_domain="my_domain.com",
                upstream_server="imap.example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
            )
        assert "mail_domain" in str(exc_info.value)

    def test_invalid_domain_with_space(self) -> None:
        """Test invalid domain containing space."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="testuser",
                mail_pass="secret",
                mail_domain="my domain.com",
                upstream_server="imap.example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
            )
        assert "mail_domain" in str(exc_info.value)


class TestUpstreamServerValidation:
    """Test upstream_server field validation pattern: ^[a-zA-Z0-9.-]+$"""

    def test_valid_upstream_server(self) -> None:
        """Test valid upstream server hostname."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.gmail.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
        )
        assert settings.upstream_server == "imap.gmail.com"

    def test_invalid_upstream_server_with_special_chars(self) -> None:
        """Test invalid upstream server with special characters."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="testuser",
                mail_pass="secret",
                mail_domain="example.com",
                upstream_server="imap://example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
            )
        assert "upstream_server" in str(exc_info.value)


class TestPortValidation:
    """Test port field validation (1-65535)."""

    def test_valid_upstream_port_default(self) -> None:
        """Test default upstream port (993)."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
        )
        assert settings.upstream_port == 993

    def test_valid_upstream_port_custom(self) -> None:
        """Test custom upstream port."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
            upstream_port=143,
        )
        assert settings.upstream_port == 143

    def test_valid_port_minimum(self) -> None:
        """Test minimum valid port (1)."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
            upstream_port=1,
        )
        assert settings.upstream_port == 1

    def test_valid_port_maximum(self) -> None:
        """Test maximum valid port (65535)."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
            upstream_port=65535,
        )
        assert settings.upstream_port == 65535

    def test_invalid_port_zero(self) -> None:
        """Test invalid port (0)."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="testuser",
                mail_pass="secret",
                mail_domain="example.com",
                upstream_server="imap.example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
                upstream_port=0,
            )
        assert "upstream_port" in str(exc_info.value)

    def test_invalid_port_too_high(self) -> None:
        """Test invalid port (65536)."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="testuser",
                mail_pass="secret",
                mail_domain="example.com",
                upstream_server="imap.example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
                upstream_port=65536,
            )
        assert "upstream_port" in str(exc_info.value)

    def test_invalid_port_negative(self) -> None:
        """Test invalid negative port."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="testuser",
                mail_pass="secret",
                mail_domain="example.com",
                upstream_server="imap.example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
                upstream_port=-1,
            )
        assert "upstream_port" in str(exc_info.value)


class TestFetchIntervalValidation:
    """Test fetch_interval field validation (10-3600)."""

    def test_valid_fetch_interval_default(self) -> None:
        """Test default fetch interval (300)."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
        )
        assert settings.fetch_interval == 300

    def test_valid_fetch_interval_minimum(self) -> None:
        """Test minimum fetch interval (10)."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
            fetch_interval=10,
        )
        assert settings.fetch_interval == 10

    def test_valid_fetch_interval_maximum(self) -> None:
        """Test maximum fetch interval (3600)."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
            fetch_interval=3600,
        )
        assert settings.fetch_interval == 3600

    def test_invalid_fetch_interval_too_low(self) -> None:
        """Test invalid fetch interval (9) below minimum."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="testuser",
                mail_pass="secret",
                mail_domain="example.com",
                upstream_server="imap.example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
                fetch_interval=9,
            )
        assert "fetch_interval" in str(exc_info.value)

    def test_invalid_fetch_interval_too_high(self) -> None:
        """Test invalid fetch interval (3601) above maximum."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="testuser",
                mail_pass="secret",
                mail_domain="example.com",
                upstream_server="imap.example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
                fetch_interval=3601,
            )
        assert "fetch_interval" in str(exc_info.value)


class TestRateLimitValidation:
    """Test rate_limit_per_minute validation (1-100)."""

    def test_valid_rate_limit_minimum(self) -> None:
        """Test minimum rate limit (1)."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
            rate_limit_per_minute=1,
        )
        assert settings.rate_limit_per_minute == 1

    def test_valid_rate_limit_maximum(self) -> None:
        """Test maximum rate limit (100)."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
            rate_limit_per_minute=100,
        )
        assert settings.rate_limit_per_minute == 100

    def test_invalid_rate_limit_zero(self) -> None:
        """Test invalid rate limit (0)."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="testuser",
                mail_pass="secret",
                mail_domain="example.com",
                upstream_server="imap.example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
                rate_limit_per_minute=0,
            )
        assert "rate_limit_per_minute" in str(exc_info.value)

    def test_invalid_rate_limit_too_high(self) -> None:
        """Test invalid rate limit (101)."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="testuser",
                mail_pass="secret",
                mail_domain="example.com",
                upstream_server="imap.example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
                rate_limit_per_minute=101,
            )
        assert "rate_limit_per_minute" in str(exc_info.value)


class TestMaxRetriesValidation:
    """Test max_retries validation (1-10)."""

    def test_valid_max_retries_minimum(self) -> None:
        """Test minimum max retries (1)."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
            max_retries=1,
        )
        assert settings.max_retries == 1

    def test_valid_max_retries_maximum(self) -> None:
        """Test maximum max retries (10)."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
            max_retries=10,
        )
        assert settings.max_retries == 10

    def test_invalid_max_retries_zero(self) -> None:
        """Test invalid max retries (0)."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="testuser",
                mail_pass="secret",
                mail_domain="example.com",
                upstream_server="imap.example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
                max_retries=0,
            )
        assert "max_retries" in str(exc_info.value)

    def test_invalid_max_retries_too_high(self) -> None:
        """Test invalid max retries (11)."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="testuser",
                mail_pass="secret",
                mail_domain="example.com",
                upstream_server="imap.example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
                max_retries=11,
            )
        assert "max_retries" in str(exc_info.value)


class TestAITimeoutValidation:
    """Test ai_timeout validation (10-120)."""

    def test_valid_ai_timeout_minimum(self) -> None:
        """Test minimum AI timeout (10)."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
            ai_timeout=10,
        )
        assert settings.ai_timeout == 10

    def test_valid_ai_timeout_maximum(self) -> None:
        """Test maximum AI timeout (120)."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
            ai_timeout=120,
        )
        assert settings.ai_timeout == 120

    def test_invalid_ai_timeout_too_low(self) -> None:
        """Test invalid AI timeout (9)."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="testuser",
                mail_pass="secret",
                mail_domain="example.com",
                upstream_server="imap.example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
                ai_timeout=9,
            )
        assert "ai_timeout" in str(exc_info.value)

    def test_invalid_ai_timeout_too_high(self) -> None:
        """Test invalid AI timeout (121)."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="testuser",
                mail_pass="secret",
                mail_domain="example.com",
                upstream_server="imap.example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
                ai_timeout=121,
            )
        assert "ai_timeout" in str(exc_info.value)


class TestBriefingHourValidation:
    """Test briefing_hour validation (0-23)."""

    def test_valid_briefing_hour_minimum(self) -> None:
        """Test minimum briefing hour (0)."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
            briefing_hour=0,
        )
        assert settings.briefing_hour == 0

    def test_valid_briefing_hour_maximum(self) -> None:
        """Test maximum briefing hour (23)."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
            briefing_hour=23,
        )
        assert settings.briefing_hour == 23

    def test_invalid_briefing_hour_negative(self) -> None:
        """Test invalid negative briefing hour."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="testuser",
                mail_pass="secret",
                mail_domain="example.com",
                upstream_server="imap.example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
                briefing_hour=-1,
            )
        assert "briefing_hour" in str(exc_info.value)

    def test_invalid_briefing_hour_too_high(self) -> None:
        """Test invalid briefing hour (24)."""
        with pytest.raises(ValidationError) as exc_info:
            create_settings(
                mail_user="testuser",
                mail_pass="secret",
                mail_domain="example.com",
                upstream_server="imap.example.com",
                upstream_user="user@example.com",
                upstream_pass="pass",
                anthropic_api_key="sk-test",
                briefing_hour=24,
            )
        assert "briefing_hour" in str(exc_info.value)


class TestSecretStrFields:
    """Test SecretStr fields hide sensitive values."""

    def test_mail_pass_is_secret(self) -> None:
        """Test mail_pass is stored as SecretStr."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="supersecret123",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
        )
        # String representation should hide the value
        assert "supersecret123" not in str(settings.mail_pass)
        # But get_secret_value() should return it
        assert settings.mail_pass.get_secret_value() == "supersecret123"

    def test_upstream_pass_is_secret(self) -> None:
        """Test upstream_pass is stored as SecretStr."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="myupstreampassword",
            anthropic_api_key="sk-test",
        )
        assert "myupstreampassword" not in str(settings.upstream_pass)
        assert settings.upstream_pass.get_secret_value() == "myupstreampassword"

    def test_anthropic_api_key_is_secret(self) -> None:
        """Test anthropic_api_key is stored as SecretStr."""
        settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-ant-api-key-12345",
        )
        assert "sk-ant-api-key-12345" not in str(settings.anthropic_api_key)
        assert settings.anthropic_api_key.get_secret_value() == "sk-ant-api-key-12345"


class TestMissingRequiredFields:
    """Test validation errors for missing required fields."""

    def test_missing_mail_user(self) -> None:
        """Test error when mail_user is missing."""
        # Clear the environment variable that conftest.py sets
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                Settings(
                    _env_file=None,
                    mail_pass="secret",
                    mail_domain="example.com",
                    upstream_server="imap.example.com",
                    upstream_user="user@example.com",
                    upstream_pass="pass",
                    anthropic_api_key="sk-test",
                )
            assert "mail_user" in str(exc_info.value)

    def test_missing_mail_pass(self) -> None:
        """Test error when mail_pass is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                Settings(
                    _env_file=None,
                    mail_user="testuser",
                    mail_domain="example.com",
                    upstream_server="imap.example.com",
                    upstream_user="user@example.com",
                    upstream_pass="pass",
                    anthropic_api_key="sk-test",
                )
            assert "mail_pass" in str(exc_info.value)

    def test_missing_anthropic_api_key(self) -> None:
        """Test error when anthropic_api_key is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                Settings(
                    _env_file=None,
                    mail_user="testuser",
                    mail_pass="secret",
                    mail_domain="example.com",
                    upstream_server="imap.example.com",
                    upstream_user="user@example.com",
                    upstream_pass="pass",
                )
            assert "anthropic_api_key" in str(exc_info.value)


class TestGetSettingsCaching:
    """Test get_settings function with lru_cache."""

    def test_get_settings_returns_settings_instance(self) -> None:
        """Test get_settings returns a Settings instance.

        Note: get_settings() loads from .env file by default, so we mock it.
        """
        # Create a mock Settings that we control
        mock_settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
        )

        with patch("postal_inspector.config.settings.Settings", return_value=mock_settings):
            get_settings.cache_clear()
            settings = get_settings()
            assert isinstance(settings, Settings)

    def test_get_settings_returns_same_instance(self) -> None:
        """Test get_settings returns the same cached instance."""
        mock_settings = create_settings(
            mail_user="testuser",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
        )

        with patch("postal_inspector.config.settings.Settings", return_value=mock_settings):
            get_settings.cache_clear()
            settings1 = get_settings()
            settings2 = get_settings()
            assert settings1 is settings2

    def test_get_settings_cache_clear(self) -> None:
        """Test that cache_clear creates a new instance."""
        # Create two distinct mock settings instances
        mock_settings1 = create_settings(
            mail_user="user1",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
        )
        mock_settings2 = create_settings(
            mail_user="user2",
            mail_pass="secret",
            mail_domain="example.com",
            upstream_server="imap.example.com",
            upstream_user="user@example.com",
            upstream_pass="pass",
            anthropic_api_key="sk-test",
        )

        get_settings.cache_clear()

        # Patch to return different instances on each call
        with patch(
            "postal_inspector.config.settings.Settings",
            side_effect=[mock_settings1, mock_settings2],
        ):
            settings1 = get_settings()
            get_settings.cache_clear()
            settings2 = get_settings()
            # They should not be the same instance since cache was cleared
            assert settings1 is not settings2
            assert settings1.mail_user == "user1"
            assert settings2.mail_user == "user2"


class TestEnvironmentVariableLoading:
    """Test loading settings from environment variables."""

    def test_settings_from_environment(self) -> None:
        """Test Settings loads from environment variables."""
        # The conftest.py already sets up test environment variables
        # Disable .env file loading to only use environment
        settings = Settings(_env_file=None)
        assert settings.mail_user == "testuser"
        assert settings.mail_domain == "test.local"
        assert settings.upstream_server == "imap.test.local"

    def test_custom_environment_override(self) -> None:
        """Test custom environment variables override defaults."""
        with patch.dict(
            os.environ,
            {
                "MAIL_USER": "customuser",
                "MAIL_PASS": "custompass",
                "MAIL_DOMAIN": "custom.local",
                "UPSTREAM_SERVER": "imap.custom.local",
                "UPSTREAM_USER": "custom@custom.local",
                "UPSTREAM_PASS": "custompass",
                "ANTHROPIC_API_KEY": "sk-custom-key",
                "FETCH_INTERVAL": "600",
                "BRIEFING_HOUR": "10",
            },
        ):
            settings = Settings(_env_file=None)
            assert settings.mail_user == "customuser"
            assert settings.mail_domain == "custom.local"
            assert settings.fetch_interval == 600
            assert settings.briefing_hour == 10
