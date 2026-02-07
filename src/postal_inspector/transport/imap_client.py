"""Async IMAP client for fetching upstream mail."""

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from datetime import datetime

import aioimaplib
import structlog

from postal_inspector.config import Settings
from postal_inspector.exceptions import DeliveryError

logger = structlog.get_logger(__name__)


class IMAPFetcher:
    """Async IMAP client using aioimaplib with auto-reconnection."""

    # Reconnection settings
    MAX_RECONNECT_ATTEMPTS = 5
    INITIAL_BACKOFF_SECONDS = 5
    MAX_BACKOFF_SECONDS = 300  # 5 minutes

    def __init__(self, settings: Settings):
        self.host = settings.upstream_server
        self.port = settings.upstream_port
        self.user = settings.upstream_user
        self.password = settings.upstream_pass.get_secret_value()
        self._client: aioimaplib.IMAP4_SSL | None = None
        self._connected = False
        self._consecutive_failures = 0
        self._last_successful_fetch: datetime | None = None
        self._last_error: str | None = None

    @property
    def is_connected(self) -> bool:
        """Check if IMAP connection is active."""
        return self._connected and self._client is not None

    @property
    def last_successful_fetch(self) -> datetime | None:
        """Return timestamp of last successful fetch."""
        return self._last_successful_fetch

    @property
    def last_error(self) -> str | None:
        """Return the last error message."""
        return self._last_error

    @property
    def consecutive_failures(self) -> int:
        """Return count of consecutive connection failures."""
        return self._consecutive_failures

    async def connect(self) -> None:
        """Establish IMAP connection."""
        logger.info("imap_connecting", host=self.host, port=self.port)
        try:
            self._client = aioimaplib.IMAP4_SSL(host=self.host, port=self.port, timeout=30)
            await self._client.wait_hello_from_server()
            await self._client.login(self.user, self.password)
            self._connected = True
            self._consecutive_failures = 0
            self._last_error = None
            logger.info("imap_connected", user=self.user)
        except Exception as e:
            self._connected = False
            self._last_error = str(e)
            logger.error("imap_connection_failed", error=str(e))
            raise DeliveryError(f"IMAP connection failed: {e}")

    async def reconnect(self) -> bool:
        """Attempt to reconnect with exponential backoff.

        Returns True if reconnection succeeded, False otherwise.
        """
        # First, clean up existing connection
        await self.disconnect()

        for attempt in range(1, self.MAX_RECONNECT_ATTEMPTS + 1):
            backoff = min(
                self.INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1)),
                self.MAX_BACKOFF_SECONDS
            )

            logger.info(
                "imap_reconnecting",
                attempt=attempt,
                max_attempts=self.MAX_RECONNECT_ATTEMPTS,
                backoff_seconds=backoff
            )

            try:
                await self.connect()
                logger.info("imap_reconnected", attempt=attempt)
                return True
            except DeliveryError:
                self._consecutive_failures += 1
                if attempt < self.MAX_RECONNECT_ATTEMPTS:
                    await asyncio.sleep(backoff)

        logger.error(
            "imap_reconnect_failed",
            attempts=self.MAX_RECONNECT_ATTEMPTS,
            consecutive_failures=self._consecutive_failures
        )
        return False

    async def disconnect(self) -> None:
        """Close IMAP connection."""
        if self._client:
            with contextlib.suppress(Exception):
                await self._client.logout()
            self._client = None
            self._connected = False
            logger.info("imap_disconnected")

    async def _ensure_archive_folder(self) -> None:
        """Ensure Archive folder exists on upstream server."""
        try:
            # Check if Archive folder exists
            status, data = await self._client.list("", "Archive")
            if status == "OK" and not data[0]:
                # Folder doesn't exist, create it
                await self._client.create("Archive")
                logger.info("archive_folder_created")
        except Exception as e:
            logger.warning("archive_folder_check_failed", error=str(e))

    async def fetch_new_messages(self) -> AsyncGenerator[tuple[str, bytes], None]:
        """Fetch all messages from INBOX and yield them for local storage.

        After yielding, caller should save locally then call delete_message()
        to remove from Migadu. This ensures no email loss.

        Raises DeliveryError if connection is lost (caller should reconnect).
        """
        if not self._client or not self._connected:
            raise DeliveryError("IMAP not connected")

        try:
            await self._client.select("INBOX")

            # Search for ALL messages (not just UNSEEN)
            status, data = await self._client.search("ALL")
            if status != "OK":
                logger.warning("imap_search_failed", status=status)
                return

            message_ids = data[0].decode().split() if data[0] else []
            logger.info("imap_messages_found", count=len(message_ids))

            # Record successful communication with server
            self._last_successful_fetch = datetime.now()

            for msg_id in message_ids:
                try:
                    status, msg_data = await self._client.fetch(msg_id, "(RFC822)")
                    if status == "OK" and msg_data:
                        # aioimaplib returns [bytes, bytearray, bytes, bytes]
                        # The email content is in the bytearray (index 1)
                        if len(msg_data) >= 2 and isinstance(msg_data[1], (bytes, bytearray)):
                            raw_email = bytes(msg_data[1])
                            logger.info("email_fetched", msg_id=msg_id, size=len(raw_email))
                            self._last_successful_fetch = datetime.now()
                            yield (msg_id, raw_email)
                            break
                except Exception as e:
                    logger.error("imap_fetch_failed", msg_id=msg_id, error=str(e))
                    continue

        except Exception as e:
            # Connection likely dropped
            self._connected = False
            self._last_error = str(e)
            self._consecutive_failures += 1
            logger.error("imap_connection_lost", error=str(e))
            raise DeliveryError(f"IMAP connection lost: {e}")

    async def delete_message(self, msg_id: str) -> None:
        """Delete a message from INBOX after saving locally.

        This removes the email from Migadu - we rely on local storage.
        """
        if not self._client:
            raise DeliveryError("IMAP not connected")

        await self._client.select("INBOX")

        try:
            await self._client.store(msg_id, "+FLAGS", "(\\Deleted)")
            await self._client.expunge()
            logger.info("email_deleted_from_migadu", msg_id=msg_id)
        except Exception as e:
            logger.warning("delete_failed", msg_id=msg_id, error=str(e))
            raise DeliveryError(f"Failed to delete message {msg_id}: {e}") from e

    async def __aenter__(self) -> "IMAPFetcher":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.disconnect()
