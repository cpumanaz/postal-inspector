from dataclasses import dataclass
from enum import Enum
from typing import Any


class Verdict(str, Enum):
    SAFE = "SAFE"
    QUARANTINE = "QUARANTINE"


@dataclass
class ScanResult:
    verdict: Verdict
    reason: str
    confidence: float | None = None
    raw_response: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict.value, "reason": self.reason, "confidence": self.confidence}
