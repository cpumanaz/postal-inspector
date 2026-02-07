"""
Pydantic Settings configuration for Postal Inspector.

Loads configuration from environment variables with validation patterns
matching the shell-based validation in services/mail-fetch/entrypoint.sh.
"""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Mail user settings
    # Pattern matches shell validation: Only [a-zA-Z0-9_-] allowed
    mail_user: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$")
    mail_pass: SecretStr = Field(...)
    # Pattern matches shell validation: Only [a-zA-Z0-9.-] allowed (hostname chars)
    mail_domain: str = Field(..., pattern=r"^[a-zA-Z0-9.-]+$")

    # Upstream IMAP settings
    # Pattern matches shell validation for UPSTREAM_SERVER
    upstream_server: str = Field(..., pattern=r"^[a-zA-Z0-9.-]+$")
    upstream_user: str = Field(...)
    upstream_pass: SecretStr = Field(...)
    # Port must be 1-65535 (shell validates numeric only)
    upstream_port: int = Field(993, ge=1, le=65535)

    # Processing settings
    # FETCH_INTERVAL must be 10-3600 seconds (matches shell validation)
    fetch_interval: int = Field(300, ge=10, le=3600)
    rate_limit_per_minute: int = Field(30, ge=1, le=100)
    max_retries: int = Field(20, ge=1, le=100)

    # LMTP delivery settings
    lmtp_host: str = Field("imap")
    lmtp_port: int = Field(24, ge=1, le=65535)

    # Anthropic AI settings
    anthropic_api_key: SecretStr = Field(...)
    anthropic_model: str = Field("claude-sonnet-4-5-20250929")
    ai_timeout: int = Field(45, ge=10, le=120)

    # Briefing settings
    briefing_hour: int = Field(8, ge=0, le=23)

    # Path settings
    maildir_path: str = Field("/var/mail")
    log_path: str = Field("/app/logs")

    # Timezone
    tz: str = Field("US/Central")

    # Logging settings
    log_format: str = Field("console")  # "json" or "console"
    debug: bool = Field(False)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Uses lru_cache to ensure only one Settings instance is created,
    avoiding repeated environment variable parsing.
    """
    return Settings()  # type: ignore[call-arg]
