from dataclasses import dataclass
from enum import Enum
from typing import Any


class Verdict(str, Enum):
    SAFE = "SAFE"
    QUARANTINE = "QUARANTINE"
    # HOLD is NOT a content verdict. It means the scan could not be completed due to
    # an API/infrastructure error (e.g. Anthropic credit balance exhausted, auth,
    # rate-limit, timeout). The email is left untouched in staging and retried on the
    # next cycle instead of being quarantined, so a billing/API lapse pauses mail
    # rather than burying legitimate mail in Quarantine.
    HOLD = "HOLD"


@dataclass
class ScanResult:
    verdict: Verdict
    reason: str
    confidence: float | None = None
    raw_response: str | None = None
    # Token usage from the Anthropic response (None when no API call was made, e.g.
    # a deterministic auth-gate verdict or an API error before any usage was returned).
    input_tokens: int | None = None
    output_tokens: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict.value, "reason": self.reason, "confidence": self.confidence}
