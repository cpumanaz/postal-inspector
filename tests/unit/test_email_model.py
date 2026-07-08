"""Tests for email model."""

from postal_inspector.models.email import ParsedEmail


def _email_with_to(to_addr: str) -> ParsedEmail:
    return ParsedEmail(
        message_id="<m@x>",
        from_addr="s@x.com",
        to_addr=to_addr,
        reply_to=None,
        subject="s",
        body_preview="b",
        raw=b"",
    )


def test_recipient_single_plain():
    assert _email_with_to("user@test.local").get_recipient_address() == "user@test.local"


def test_recipient_single_with_name():
    assert _email_with_to("Bob <bob@test.local>").get_recipient_address() == "bob@test.local"


def test_recipient_multi_falls_back_to_local():
    # Multi-recipient family forward must NOT produce a broken RCPT TO;
    # returns "" so the caller delivers to the local mailbox instead.
    to = "Ethan <ethan@outlook.com>, \r\n\tMatthew <matthew@outlook.com>"
    assert _email_with_to(to).get_recipient_address() == ""


def test_recipient_empty_or_malformed():
    assert _email_with_to("").get_recipient_address() == ""
    assert _email_with_to("undisclosed-recipients:;").get_recipient_address() == ""


def test_parse_simple_email(sample_email_bytes):
    email = ParsedEmail.parse(sample_email_bytes)
    assert email.from_addr == "sender@example.com"
    assert email.to_addr == "recipient@test.local"
    assert email.subject == "Test Email"
    assert "test email body" in email.body_preview.lower()


def test_parse_extracts_message_id(sample_email_bytes):
    email = ParsedEmail.parse(sample_email_bytes)
    assert "<test-123@example.com>" in email.message_id
