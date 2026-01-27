"""Pytest configuration and fixtures."""

import os

import pytest

# Set test environment variables before importing settings
os.environ.update(
    {
        "MAIL_USER": "testuser",
        "MAIL_PASS": "testpass",
        "MAIL_DOMAIN": "test.local",
        "UPSTREAM_SERVER": "imap.test.local",
        "UPSTREAM_USER": "test@test.local",
        "UPSTREAM_PASS": "testpass",
        "ANTHROPIC_API_KEY": "sk-test-key",
    }
)


@pytest.fixture
def mock_settings():
    """Mock Settings object."""
    from postal_inspector.config import Settings

    return Settings()


@pytest.fixture
def sample_email_bytes():
    """Sample raw email bytes."""
    return b"""From: sender@example.com
To: recipient@test.local
Subject: Test Email
Message-ID: <test-123@example.com>
Content-Type: text/plain

This is a test email body.
"""


@pytest.fixture
def phishing_email_bytes():
    """Sample phishing email."""
    return b"""From: security@amaz0n-support.com
To: victim@test.local
Subject: URGENT: Verify your account NOW!
Message-ID: <phish-456@fake.local>
Content-Type: text/plain

Your account has been suspended. Click here to verify.
"""
