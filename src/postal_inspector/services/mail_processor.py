"""Main mail processing service."""

import asyncio
import contextlib
from datetime import date, datetime
from typing import TYPE_CHECKING

import structlog

from postal_inspector.exceptions import DeliveryError
from postal_inspector.models import ParsedEmail
from postal_inspector.scanner import AIAnalyzer, Verdict
from postal_inspector.scanner.verdict import ScanResult
from postal_inspector.transport import IMAPFetcher, LMTPDelivery, MaildirManager

if TYPE_CHECKING:
    from postal_inspector.config import Settings

logger = structlog.get_logger(__name__)


class MailProcessor:
    """Main async mail processing orchestrator."""

    def __init__(self, settings: "Settings"):
        self.settings = settings
        self.imap = IMAPFetcher(settings)
        self.analyzer = AIAnalyzer(settings)
        self.lmtp = LMTPDelivery(settings)
        self.maildir = MaildirManager(settings)
        self._shutdown = asyncio.Event()
        self._retry_counts: dict[str, int] = {}
        self.max_retries = settings.max_retries

        # API-health / token tracking, surfaced in the shared status file so the
        # daily-briefing pod can report it (both pods share the maildir PVC).
        self._last_api_error: str | None = None
        self._last_api_error_at: datetime | None = None
        # message_ids currently held awaiting API recovery (size = held count).
        self._held_message_ids: set[str] = set()
        # Rolling per-day token usage; resets when the calendar day changes.
        self._token_date: date | None = None
        self._tokens_input = 0
        self._tokens_output = 0
        self._scans_today = 0

    async def run(self) -> None:
        """Main processing loop."""
        logger.info("mail_processor_starting")

        await self.maildir.ensure_directories()

        try:
            await self.imap.connect()
            await self._write_status()

            while not self._shutdown.is_set():
                try:
                    await self._process_cycle()
                except DeliveryError as e:
                    # Connection-related error - try to reconnect
                    logger.error("cycle_error_reconnecting", error=str(e))
                    await self._write_status()
                    if not await self.imap.reconnect():
                        logger.error(
                            "reconnect_failed_waiting", wait_seconds=self.settings.fetch_interval
                        )
                except Exception as e:
                    logger.error("cycle_error", error=str(e), error_type=type(e).__name__)

                # Write status after each cycle
                await self._write_status()

                # Wait for next cycle or shutdown
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(
                        self._shutdown.wait(), timeout=self.settings.fetch_interval
                    )
        finally:
            await self.imap.disconnect()
            logger.info("mail_processor_stopped")

    async def _write_status(self) -> None:
        """Write current status to file for health monitoring."""
        await self.maildir.write_processor_status(
            last_successful_fetch=self.imap.last_successful_fetch,
            consecutive_failures=self.imap.consecutive_failures,
            last_error=self.imap.last_error,
            is_connected=self.imap.is_connected,
            last_api_error=self._last_api_error,
            last_api_error_at=self._last_api_error_at,
            held_count=len(self._held_message_ids),
            tokens_input_today=self._tokens_input,
            tokens_output_today=self._tokens_output,
            scans_today=self._scans_today,
        )

    def _record_usage(self, result: ScanResult) -> None:
        """Accumulate token usage for the current day (resets at day rollover)."""
        if result.input_tokens is None and result.output_tokens is None:
            return  # No API call was made (e.g. deterministic auth-gate verdict).
        today = datetime.now().date()
        if self._token_date != today:
            self._token_date = today
            self._tokens_input = 0
            self._tokens_output = 0
            self._scans_today = 0
        self._tokens_input += result.input_tokens or 0
        self._tokens_output += result.output_tokens or 0
        self._scans_today += 1

    def _note_api_recovered(self, message_id: str) -> None:
        """A real API round-trip succeeded: clear the outage flag for this message."""
        self._last_api_error = None
        self._last_api_error_at = None
        self._held_message_ids.discard(message_id)

    async def _process_cycle(self) -> None:
        """Single fetch-scan-deliver cycle.

        1. Process any emails in staging (retries from previous failures)
        2. Fetch new emails from the upstream server
        3. Save locally to staging (verified)
        4. Delete from the upstream server (only after verified)
        5. Process from staging
        6. On success: Move to .delivered archive (NEVER delete)
        7. On failure: Leave in staging for retry (NEVER delete)
        """
        # First, retry any emails stuck in staging
        await self._process_staging()

        # Then fetch and process new emails from upstream
        async for msg_id, raw_email in self.imap.fetch_new_messages():
            if self._shutdown.is_set():
                break

            # Save locally immediately with verification
            try:
                staging_filename = await self.maildir.save_to_staging(raw_email)
                logger.info("email_saved_locally", size=len(raw_email), filename=staging_filename)
            except Exception as e:
                logger.error("staging_save_failed", error=str(e))
                continue  # Don't delete from upstream if save failed

            # Delete from the upstream server now that we have verified local copy
            try:
                await self.imap.delete_message(msg_id)
            except Exception as e:
                logger.error("upstream_delete_failed", msg_id=msg_id, error=str(e))
                # Continue processing even if delete fails

            # Process the email - it will be moved to appropriate folder
            # (delivered/quarantine/failed), never deleted
            await self._process_email(raw_email, staging_filename)

    async def _process_staging(self) -> None:
        """Process emails in staging (retries from previous failures)."""
        staging_emails = await self.maildir.get_staging_emails()
        if staging_emails:
            logger.info("processing_staging", count=len(staging_emails))

        for staging_filename, raw_email in staging_emails:
            if self._shutdown.is_set():
                break
            await self._process_email(raw_email, staging_filename)

    async def _process_email(self, raw_email: bytes, staging_filename: str) -> None:
        """Process single email: parse -> scan -> deliver/quarantine.

        Email is in staging. On success, moved to appropriate folder.
        On failure, left in staging for retry. NEVER deleted.

        Args:
            raw_email: The raw email bytes
            staging_filename: Filename in staging folder
        """
        try:
            email = ParsedEmail.parse(raw_email)
        except Exception as e:
            logger.error("parse_failed", error=str(e))
            await self.maildir.move_to_failed(raw_email, f"Parse error: {e}")
            await self.maildir.remove_from_staging(staging_filename)
            return

        logger.info("processing_email", subject=email.subject[:50], from_addr=email.from_addr[:50])

        # AI scan
        result = await self.analyzer.analyze_email(email)
        self._record_usage(result)

        if result.verdict == Verdict.HOLD:
            # API/infra failure (e.g. credit balance exhausted): the email was NOT
            # scanned. Leave it in staging so it is retried next cycle instead of
            # being quarantined. Record the error so the daily briefing can report it.
            self._last_api_error = result.reason
            self._last_api_error_at = datetime.now()
            self._held_message_ids.add(email.message_id)
            logger.warning(
                "email_held",
                reason=result.reason,
                held_count=len(self._held_message_ids),
                subject=email.subject[:50],
            )
            # Return the claimed .processing file to .mail so it is picked up again.
            if staging_filename.endswith(".processing"):
                await self.maildir.restore_to_staging(staging_filename)
            return

        # A real verdict means the API round-trip succeeded — clear any outage flag.
        self._note_api_recovered(email.message_id)

        if result.verdict == Verdict.QUARANTINE:
            # Move to quarantine folder
            await self.maildir.quarantine(raw_email, result.reason)
            await self.maildir.remove_from_staging(staging_filename)
            self._clear_retry(email.message_id)
        else:
            # Deliver via LMTP
            success = await self._deliver_with_retry(raw_email, email)
            if success:
                # Remove from staging (delivered or moved to .failed)
                await self.maildir.remove_from_staging(staging_filename)
            else:
                # Restore .processing back to .mail for next retry
                if staging_filename.endswith(".processing"):
                    await self.maildir.restore_to_staging(staging_filename)

    async def _deliver_with_retry(self, raw_email: bytes, email: ParsedEmail) -> bool:
        """Attempt LMTP delivery with retry tracking.

        Returns:
            True if delivery succeeded OR max retries exceeded (moved to .failed).
            False if delivery failed and should stay in staging for retry.
        """
        try:
            # Prefer the original To: address so Dovecot Sieve rules can route to folders,
            # but only if it is a real, deliverable address. Headers like
            # "undisclosed-recipients:;" (or an empty/malformed To:) are NOT valid LMTP
            # recipients and were causing delivery to fail into .failed. Fall back to the
            # local mailbox (mail_user) in that case so the mail is still delivered.
            recipient: str | None = email.get_recipient_address()
            if "@" not in (recipient or ""):
                logger.info("recipient_fallback_to_local", parsed=(recipient or "")[:60])
                recipient = None  # LMTPClient delivers to settings.mail_user
            success = await self.lmtp.deliver(raw_email, recipient_override=recipient)
            if success:
                # Archive to .delivered for record keeping (never delete)
                await self.maildir.archive_delivered(raw_email, email.message_id)
                self._clear_retry(email.message_id)
                logger.info("email_delivered", message_id=email.message_id[:30])
                return True
            else:
                # Temporary failure - check retry count
                return await self._handle_delivery_failure(
                    raw_email, email, "LMTP temporary failure"
                )
        except DeliveryError as e:
            # Permanent failure - check retry count
            return await self._handle_delivery_failure(raw_email, email, str(e))

    async def _handle_delivery_failure(
        self, raw_email: bytes, email: ParsedEmail, reason: str
    ) -> bool:
        """Handle delivery failure with retry count.

        Returns:
            True if max retries exceeded (email moved to .failed, don't retry).
            False if still retrying.
        """
        count = self._increment_retry(email.message_id)
        if count >= self.max_retries:
            logger.error("max_retries_exceeded", message_id=email.message_id[:30], retries=count)
            await self.maildir.move_to_failed(raw_email, f"Max retries ({count}): {reason}")
            self._clear_retry(email.message_id)
            return True  # Don't retry, moved to .failed
        else:
            logger.warning(
                "delivery_failed_retry",
                message_id=email.message_id[:30],
                attempt=count,
                max_retries=self.max_retries,
            )
            return False  # Keep retrying

    def _increment_retry(self, message_id: str) -> int:
        """Increment retry count for message."""
        self._retry_counts[message_id] = self._retry_counts.get(message_id, 0) + 1
        return self._retry_counts[message_id]

    def _clear_retry(self, message_id: str) -> None:
        """Clear retry count for message."""
        self._retry_counts.pop(message_id, None)

    def request_shutdown(self) -> None:
        """Signal graceful shutdown."""
        logger.info("shutdown_requested")
        self._shutdown.set()
