"""AI-powered email security analyzer using Anthropic SDK."""

import re
from typing import TYPE_CHECKING

import anthropic
import structlog
from anthropic.types import TextBlock
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from postal_inspector.core import RateLimiter
from postal_inspector.scanner.auth_check import authentication_verdict
from postal_inspector.scanner.prompts import build_scan_prompt
from postal_inspector.scanner.verdict import ScanResult, Verdict

if TYPE_CHECKING:
    from postal_inspector.config import Settings
    from postal_inspector.models import ParsedEmail

logger = structlog.get_logger(__name__)

# Lenient verdict parser: find the verdict keyword (optionally followed by a
# separator and a reason) anywhere near the start of the response. This avoids
# the previous strict single-line regex, which fail-closed to QUARANTINE on any
# formatting deviation and caused legitimate mail to be quarantined.
VERDICT_PATTERN = re.compile(
    r"\b(SAFE|QUARANTINE)\b[\s:|.\-]*(.{0,100})", re.IGNORECASE
)


class AIAnalyzer:
    """Anthropic SDK integration for email security scanning."""

    def __init__(self, settings: "Settings") -> None:
        """Initialize the AI analyzer with settings.

        Args:
            settings: Application settings containing API key and model config.
        """
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value()
        )
        self.model = settings.anthropic_model
        self.timeout = settings.ai_timeout
        self.rate_limiter = RateLimiter(settings.rate_limit_per_minute)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=8),
        retry=retry_if_exception_type((anthropic.APITimeoutError, anthropic.APIConnectionError)),
        reraise=True,
    )
    async def _call_api(self, prompt: str) -> str:
        """Call Anthropic API with retry logic.

        Retries up to 3 times with exponential backoff (2s, 4s, 8s)
        on timeout or connection errors.

        Args:
            prompt: The prompt to send to Claude.

        Returns:
            The text response from Claude.

        Raises:
            anthropic.APIError: On API errors after retries exhausted.
        """
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=256,
            timeout=self.timeout,
            messages=[{"role": "user", "content": prompt}],
        )
        content_block = response.content[0]
        if isinstance(content_block, TextBlock):
            return content_block.text.strip()
        raise ValueError(f"Unexpected content type: {type(content_block)}")

    def _parse_response(self, text: str) -> ScanResult:
        """Parse and validate AI response.

        Searches for a valid verdict line in the format:
        SAFE|reason or QUARANTINE|reason

        FAIL-CLOSED: Returns QUARANTINE if no valid response found.

        Args:
            text: Raw response text from Claude.

        Returns:
            ScanResult with parsed verdict and reason.
        """
        # Find the first verdict keyword (the model is told to put it first).
        match = VERDICT_PATTERN.search(text)
        if match:
            verdict_str = match.group(1).upper()
            reason = (match.group(2) or "").strip().strip(":|.-  ")[:100]
            verdict = Verdict.SAFE if verdict_str == "SAFE" else Verdict.QUARANTINE
            return ScanResult(
                verdict=verdict,
                reason=reason or verdict_str.title(),
                raw_response=text,
            )

        # No verdict found - fail closed
        logger.warning("invalid_ai_response", response=text[:100])
        return ScanResult(
            verdict=Verdict.QUARANTINE,
            reason="Invalid AI response format",
            raw_response=text,
        )

    async def analyze_email(self, email: "ParsedEmail") -> ScanResult:
        """Analyze email for security threats using Claude.

        FAIL-CLOSED: Returns QUARANTINE on any error to ensure
        potentially malicious emails are never auto-delivered.

        Args:
            email: Parsed email to analyze.

        Returns:
            ScanResult with verdict (SAFE or QUARANTINE) and reason.
        """
        # Deterministic authentication gate (keys on DMARC + DKIM alignment, NOT SPF,
        # so forwarded mail is unaffected). A hard DMARC failure is a definite spoof and
        # is quarantined without spending an AI call. dmarc=none with no aligned DKIM is
        # "unauthenticated": not auto-blocked (some legitimate senders lack DMARC), but
        # passed to the AI as a strong signal to scrutinize and lean toward QUARANTINE.
        auth_status, auth_detail = authentication_verdict(email)
        if auth_status == "spoofed":
            logger.info("auth_gate_spoofed", detail=auth_detail, subject=email.subject[:50])
            return ScanResult(
                verdict=Verdict.QUARANTINE,
                reason=f"Spoofed sender: {auth_detail}"[:100],
            )
        auth_label = {
            "pass": "AUTHENTICATED (DMARC pass / DKIM aligned to the sender domain)",
            "unauthenticated": (
                "UNAUTHENTICATED (no DMARC policy AND no DKIM aligned to the sender domain)"
            ),
            "unknown": "UNKNOWN (no authentication data available)",
        }.get(auth_status, auth_status)

        # Rate limiting
        await self.rate_limiter.acquire()

        # Build prompt
        prompt = build_scan_prompt(
            from_addr=email.from_addr,
            to_addr=email.to_addr,
            reply_to=email.reply_to,
            subject=email.subject,
            body_preview=email.body_preview,
            return_path=email.return_path,
            auth_results=email.auth_results,
            auth_status=auth_label,
        )

        logger.info("scanning_email", subject=email.subject[:50], auth=auth_status)

        try:
            raw_response = await self._call_api(prompt)
            result = self._parse_response(raw_response)
            logger.info(
                "scan_complete",
                verdict=result.verdict.value,
                reason=result.reason,
            )
            return result

        except anthropic.APIError as e:
            logger.error("ai_api_error", error=str(e))
            return ScanResult(
                verdict=Verdict.QUARANTINE,
                reason=f"AI API error: {str(e)[:40]}",
            )
        except Exception as e:
            # FAIL-CLOSED: Any unexpected error = QUARANTINE
            logger.error("ai_analysis_failed", error=str(e))
            return ScanResult(
                verdict=Verdict.QUARANTINE,
                reason=f"Analysis failed: {str(e)[:40]}",
            )
