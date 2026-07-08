"""Tests for verdict module."""

from postal_inspector.scanner.verdict import ScanResult, Verdict


def test_verdict_values():
    assert Verdict.SAFE.value == "SAFE"
    assert Verdict.QUARANTINE.value == "QUARANTINE"
    assert Verdict.HOLD.value == "HOLD"


def test_scan_result_token_fields_default_none():
    result = ScanResult(verdict=Verdict.SAFE, reason="ok")
    assert result.input_tokens is None
    assert result.output_tokens is None


def test_scan_result_carries_token_usage():
    result = ScanResult(verdict=Verdict.SAFE, reason="ok", input_tokens=1200, output_tokens=8)
    assert result.input_tokens == 1200
    assert result.output_tokens == 8


def test_scan_result_to_dict():
    result = ScanResult(verdict=Verdict.SAFE, reason="Test reason")
    d = result.to_dict()
    assert d["verdict"] == "SAFE"
    assert d["reason"] == "Test reason"
    assert d["confidence"] is None


def test_scan_result_with_confidence():
    result = ScanResult(verdict=Verdict.QUARANTINE, reason="Phishing", confidence=0.95)
    d = result.to_dict()
    assert d["confidence"] == 0.95
