"""Tests for prompt module."""

from postal_inspector.scanner.prompts import build_scan_prompt, sanitize_for_prompt


def test_sanitize_removes_control_chars():
    assert sanitize_for_prompt("hello\x00world") == "helloworld"
    assert sanitize_for_prompt("test\x1b[31mred") == "testred"


def test_sanitize_removes_injection_patterns():
    assert "---" not in sanitize_for_prompt("test---injection")
    assert "===" not in sanitize_for_prompt("test===break")
    assert "```" not in sanitize_for_prompt("test```code")


def test_sanitize_max_length():
    long_text = "a" * 500
    result = sanitize_for_prompt(long_text, max_length=100)
    assert len(result) == 100


def test_build_scan_prompt_fills_placeholders():
    prompt = build_scan_prompt(
        from_addr="test@example.com",
        to_addr="user@local.com",
        reply_to="reply@example.com",
        subject="Test Subject",
        body_preview="Test body",
    )
    assert "test@example.com" in prompt
    assert "Test Subject" in prompt
    assert "SAFE" in prompt
    assert "QUARANTINE" in prompt
