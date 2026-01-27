"""Maildir operations for email storage."""

import hashlib
import os
import socket
import time
from pathlib import Path

import aiofiles
import aiofiles.os
import structlog

from postal_inspector.config import Settings
from postal_inspector.exceptions import DeliveryError

logger = structlog.get_logger(__name__)


class MaildirManager:
    """Manage Maildir operations: quarantine, archive, failed."""

    def __init__(self, settings: Settings):
        self.maildir_path = Path(settings.maildir_path)
        self.mail_user = settings.mail_user
        self.user_maildir = self.maildir_path / self.mail_user
        self.staging_dir = self.maildir_path / ".staging"

    async def ensure_directories(self) -> None:
        """Create required Maildir structure."""
        dirs = [
            self.user_maildir / ".Quarantine" / "cur",
            self.user_maildir / ".Quarantine" / "new",
            self.user_maildir / ".Quarantine" / "tmp",
            self.staging_dir,  # Staging folder for new/retry emails
            self.staging_dir / ".delivered",
            self.staging_dir / ".failed",
        ]
        for dir_path in dirs:
            await aiofiles.os.makedirs(dir_path, exist_ok=True)
        logger.info("maildir_directories_ensured")

    async def save_to_staging(self, raw_email: bytes) -> str:
        """Save email to staging folder and verify integrity.

        Verifies the file was written completely before returning.
        This ensures we have the email locally before deleting from upstream.

        Returns the filename for tracking.
        Raises DeliveryError if save fails or verification fails.
        """
        filename = f"{self._generate_filename()}.mail"
        dest_path = self.staging_dir / filename
        expected_size = len(raw_email)

        try:
            async with aiofiles.open(dest_path, "wb") as f:
                await f.write(raw_email)

            dest_path.chmod(0o660)

            # Verify the file was written correctly
            actual_size = dest_path.stat().st_size
            if actual_size != expected_size:
                raise DeliveryError(
                    f"File size mismatch: expected {expected_size}, got {actual_size}"
                )

            return filename
        except Exception as e:
            logger.error("staging_save_failed", error=str(e))
            # Clean up partial file if it exists
            if dest_path.exists():
                try:
                    await aiofiles.os.remove(dest_path)
                except Exception:
                    pass
            raise DeliveryError(f"Failed to save to staging: {e}")

    async def remove_from_staging(self, filename: str) -> None:
        """Remove email from staging after successful processing.

        Filename may have either .mail or .processing suffix.
        """
        file_path = self.staging_dir / filename
        try:
            if file_path.exists():
                await aiofiles.os.remove(file_path)
                logger.debug("staging_removed", filename=filename)
        except Exception as e:
            logger.warning("staging_remove_failed", filename=filename, error=str(e))

    async def restore_to_staging(self, processing_filename: str) -> None:
        """Restore a .processing file back to .mail for retry.

        Used when processing fails and we want to retry later.
        """
        processing_path = self.staging_dir / processing_filename
        mail_path = processing_path.with_suffix(".mail")
        try:
            if processing_path.exists():
                processing_path.rename(mail_path)
                logger.debug("staging_restored", filename=mail_path.name)
        except Exception as e:
            logger.warning("staging_restore_failed", filename=processing_filename, error=str(e))

    async def get_staging_emails(self) -> list[tuple[str, bytes]]:
        """Get all emails from staging for retry processing.

        Atomically renames files to .processing to prevent race conditions
        with new emails being saved.

        Returns:
            List of (filename, raw_email_bytes) tuples with .processing suffix.
        """
        emails = []
        try:
            staging_files = [
                f for f in self.staging_dir.iterdir()
                if f.is_file() and f.suffix == ".mail"
            ]

            for file_path in staging_files:
                try:
                    # Atomically rename to .processing to claim it
                    processing_path = file_path.with_suffix(".processing")
                    try:
                        file_path.rename(processing_path)
                    except FileNotFoundError:
                        # File was already renamed by another process
                        continue

                    # Read the email
                    async with aiofiles.open(processing_path, "rb") as f:
                        raw_email = await f.read()
                    emails.append((processing_path.name, raw_email))

                except Exception as e:
                    logger.warning("staging_read_failed", filename=file_path.name, error=str(e))

        except Exception as e:
            logger.error("staging_scan_failed", error=str(e))

        return emails

    def _generate_filename(self, message_id: str | None = None) -> str:
        """Generate unique Maildir-compliant filename."""
        timestamp = int(time.time() * 1000000)
        hostname = socket.gethostname()[:16]
        random_part = hashlib.md5(
            f"{timestamp}{os.getpid()}{message_id or ''}".encode()
        ).hexdigest()[:16]
        return f"{timestamp}.{random_part}.{hostname}"

    async def quarantine(self, raw_email: bytes, reason: str) -> str:
        """Move email to Quarantine folder."""
        filename = self._generate_filename()
        dest_path = self.user_maildir / ".Quarantine" / "cur" / filename

        try:
            async with aiofiles.open(dest_path, "wb") as f:
                await f.write(raw_email)

            # Set permissions to 660 (sync is fine - fast operation)
            dest_path.chmod(0o660)

            logger.info("email_quarantined", filename=filename, reason=reason[:50])
            return filename
        except Exception as e:
            logger.error("quarantine_failed", error=str(e))
            raise DeliveryError(f"Failed to quarantine: {e}")

    async def archive_delivered(self, raw_email: bytes, message_id: str) -> str:
        """Archive successfully delivered email to .delivered."""
        filename = self._generate_filename(message_id)
        dest_path = self.staging_dir / ".delivered" / f"{filename}.mail"

        try:
            async with aiofiles.open(dest_path, "wb") as f:
                await f.write(raw_email)

            logger.info("email_archived", filename=filename)
            return filename
        except Exception as e:
            logger.warning("archive_failed", error=str(e))
            # Archive failure is not critical - don't raise
            return ""

    async def move_to_failed(self, raw_email: bytes, reason: str) -> str:
        """Move permanently failed email to .failed folder."""
        filename = self._generate_filename()
        dest_path = self.staging_dir / ".failed" / f"{filename}.mail"

        try:
            async with aiofiles.open(dest_path, "wb") as f:
                await f.write(raw_email)

            logger.error("email_failed_permanently", filename=filename, reason=reason[:50])
            return filename
        except Exception as e:
            logger.error("move_to_failed_error", error=str(e))
            raise DeliveryError(f"Failed to move to failed: {e}")

    async def count_staging(self) -> int:
        """Count emails in staging folder."""
        try:
            count = 0
            staging = self.staging_dir
            if await aiofiles.os.path.exists(staging):
                for entry in await aiofiles.os.listdir(staging):
                    if entry.endswith(".mail"):
                        count += 1
            return count
        except Exception:
            return 0

    async def count_failed(self) -> int:
        """Count emails in failed folder."""
        try:
            failed_dir = self.staging_dir / ".failed"
            if await aiofiles.os.path.exists(failed_dir):
                entries = await aiofiles.os.listdir(failed_dir)
                return len([e for e in entries if e.endswith(".mail")])
            return 0
        except Exception:
            return 0
