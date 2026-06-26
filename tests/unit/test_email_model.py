"""Tests for email model."""

from postal_inspector.models.email import ParsedEmail


def test_parse_simple_email(sample_email_bytes):
    email = ParsedEmail.parse(sample_email_bytes)
    assert email.from_addr == "sender@example.com"
    assert email.to_addr == "recipient@test.local"
    assert email.subject == "Test Email"
    assert "test email body" in email.body_preview.lower()


def test_parse_extracts_message_id(sample_email_bytes):
    email = ParsedEmail.parse(sample_email_bytes)
    assert "<test-123@example.com>" in email.message_id
