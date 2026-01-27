"""Main mail processing service."""

import asyncio
import contextlib
from typing import TYPE_CHECKING

import structlog

from postal_inspector.exceptions import DeliveryError
from postal_inspector.models import ParsedEmail
from postal_inspector.scanner import AIAnalyzer, Verdict
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

    async def run(self) -> None:
        """Main processing loop."""
        logger.info("mail_processor_starting")

        await self.maildir.ensure_directories()

        try:
            await self.imap.connect()

            while not self._shutdown.is_set():
                try:
                    await self._process_cycle()
                except Exception as e:
                    logger.error("cycle_error", error=str(e))

                # Wait for next cycle or shutdown
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(
                        self._shutdown.wait(), timeout=self.settings.fetch_interval
                    )
        finally:
            await self.imap.disconnect()
            logger.info("mail_processor_stopped")

    async def _process_cycle(self) -> None:
        """Single fetch-scan-deliver cycle.

        1. Process any emails in staging (retries from previous failures)
        2. Fetch new emails from Migadu
        3. Save locally to staging (verified)
        4. Delete from Migadu (only after verified)
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

            # Delete from Migadu now that we have verified local copy
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
            # Pass the original To: address so Dovecot Sieve rules can route to folders
            # Extract just the email address (not the full header with display name)
            recipient = email.get_recipient_address()
            success = await self.lmtp.deliver(raw_email, recipient_override=recipient)
            if success:
                # Archive to .delivered for record keeping (never delete)
                await self.maildir.archive_delivered(raw_email, email.message_id)
                self._clear_retry(email.message_id)
                logger.info("email_delivered", message_id=email.message_id[:30])
                return True
            else:
                # Temporary failure - check retry count
                return await self._handle_delivery_failure(raw_email, email, "LMTP temporary failure")
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
