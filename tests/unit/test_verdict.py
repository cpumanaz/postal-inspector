"""Tests for verdict module."""

from postal_inspector.scanner.verdict import ScanResult, Verdict


def test_verdict_values():
    assert Verdict.SAFE.value == "SAFE"
    assert Verdict.QUARANTINE.value == "QUARANTINE"


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
