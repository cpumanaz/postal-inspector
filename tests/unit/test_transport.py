"""Tests for transport modules: maildir, lmtp_client, and imap_client."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from postal_inspector.exceptions import DeliveryError

# ==============================================================================
# MaildirManager Tests
# ==============================================================================


class TestMaildirManager:
    """Tests for MaildirManager class."""

    @pytest.fixture
    def mock_maildir_settings(self, tmp_path: Path) -> MagicMock:
        """Create mock settings for MaildirManager."""
        settings = MagicMock()
        settings.maildir_path = str(tmp_path)
        settings.mail_user = "testuser"
        return settings

    @pytest.fixture
    def maildir_manager(self, mock_maildir_settings: MagicMock):
        """Create MaildirManager instance."""
        from postal_inspector.transport.maildir import MaildirManager

        return MaildirManager(mock_maildir_settings)

    def test_init_sets_paths_correctly(
        self, mock_maildir_settings: MagicMock, tmp_path: Path
    ) -> None:
        """Test that MaildirManager initializes paths correctly."""
        from postal_inspector.transport.maildir import MaildirManager

        manager = MaildirManager(mock_maildir_settings)

        assert manager.maildir_path == tmp_path
        assert manager.mail_user == "testuser"
        assert manager.user_maildir == tmp_path / "testuser"
        assert manager.staging_dir == tmp_path / ".staging"

    @pytest.mark.asyncio
    async def test_ensure_directories_creates_structure(
        self, maildir_manager, tmp_path: Path
    ) -> None:
        """Test that ensure_directories creates the expected directory structure."""
        await maildir_manager.ensure_directories()

        # Check Quarantine directories
        assert (tmp_path / "testuser" / ".Quarantine" / "cur").exists()
        assert (tmp_path / "testuser" / ".Quarantine" / "new").exists()
        assert (tmp_path / "testuser" / ".Quarantine" / "tmp").exists()

        # Check staging directories
        assert (tmp_path / ".staging" / ".delivered").exists()
        assert (tmp_path / ".staging" / ".failed").exists()

    def test_generate_filename_is_unique(self, maildir_manager) -> None:
        """Test that generated filenames are unique."""
        filename1 = maildir_manager._generate_filename()
        filename2 = maildir_manager._generate_filename()

        assert filename1 != filename2

    def test_generate_filename_with_message_id(self, maildir_manager) -> None:
        """Test filename generation with message_id."""
        filename = maildir_manager._generate_filename("<test@example.com>")

        assert isinstance(filename, str)
        assert len(filename) > 0

    def test_generate_filename_format(self, maildir_manager) -> None:
        """Test that filename follows Maildir format: timestamp.random.hostname."""
        filename = maildir_manager._generate_filename()
        parts = filename.split(".")

        assert len(parts) == 3
        # First part should be timestamp (numeric)
        assert parts[0].isdigit()
        # Second part should be hex hash
        assert all(c in "0123456789abcdef" for c in parts[1])

    @pytest.mark.asyncio
    async def test_quarantine_writes_file(self, maildir_manager, tmp_path: Path) -> None:
        """Test that quarantine writes email to Quarantine folder."""
        await maildir_manager.ensure_directories()

        raw_email = b"From: test@example.com\nSubject: Test\n\nBody"
        filename = await maildir_manager.quarantine(raw_email, "Phishing detected")

        quarantine_path = tmp_path / "testuser" / ".Quarantine" / "cur" / filename
        assert quarantine_path.exists()
        assert quarantine_path.read_bytes() == raw_email

    @pytest.mark.asyncio
    async def test_quarantine_sets_permissions(self, maildir_manager, tmp_path: Path) -> None:
        """Test that quarantine sets correct file permissions (660)."""
        await maildir_manager.ensure_directories()

        raw_email = b"Test email content"
        filename = await maildir_manager.quarantine(raw_email, "Test reason")

        quarantine_path = tmp_path / "testuser" / ".Quarantine" / "cur" / filename
        # Check permissions (660 = owner rw, group rw)
        assert (quarantine_path.stat().st_mode & 0o777) == 0o660

    @pytest.mark.asyncio
    async def test_quarantine_returns_filename(self, maildir_manager) -> None:
        """Test that quarantine returns the generated filename."""
        await maildir_manager.ensure_directories()

        filename = await maildir_manager.quarantine(b"email", "reason")

        assert isinstance(filename, str)
        assert len(filename) > 0

    @pytest.mark.asyncio
    async def test_quarantine_failure_raises_delivery_error(self, maildir_manager) -> None:
        """Test that quarantine raises DeliveryError on write failure."""
        # Don't create directories, so write will fail
        with pytest.raises(DeliveryError) as exc_info:
            await maildir_manager.quarantine(b"email", "reason")

        assert "Failed to quarantine" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_archive_delivered_writes_file(self, maildir_manager, tmp_path: Path) -> None:
        """Test that archive_delivered writes email to .delivered folder."""
        await maildir_manager.ensure_directories()

        raw_email = b"Delivered email content"
        await maildir_manager.archive_delivered(raw_email, "<msg-123@example.com>")

        # Find the file in .delivered
        delivered_dir = tmp_path / ".staging" / ".delivered"
        files = list(delivered_dir.glob("*.mail"))
        assert len(files) == 1
        assert files[0].read_bytes() == raw_email

    @pytest.mark.asyncio
    async def test_archive_delivered_failure_returns_empty_string(self, maildir_manager) -> None:
        """Test that archive_delivered returns empty string on failure (non-critical)."""
        # Don't create directories, so write will fail
        result = await maildir_manager.archive_delivered(b"email", "msg-id")

        # Should return empty string, not raise
        assert result == ""

    @pytest.mark.asyncio
    async def test_move_to_failed_writes_file(self, maildir_manager, tmp_path: Path) -> None:
        """Test that move_to_failed writes email to .failed folder."""
        await maildir_manager.ensure_directories()

        raw_email = b"Failed email content"
        await maildir_manager.move_to_failed(raw_email, "Max retries exceeded")

        # Find the file in .failed
        failed_dir = tmp_path / ".staging" / ".failed"
        files = list(failed_dir.glob("*.mail"))
        assert len(files) == 1
        assert files[0].read_bytes() == raw_email

    @pytest.mark.asyncio
    async def test_move_to_failed_raises_delivery_error_on_failure(self, maildir_manager) -> None:
        """Test that move_to_failed raises DeliveryError on write failure."""
        # Don't create directories, so write will fail
        with pytest.raises(DeliveryError) as exc_info:
            await maildir_manager.move_to_failed(b"email", "reason")

        assert "Failed to move to failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_count_staging_with_files(self, maildir_manager, tmp_path: Path) -> None:
        """Test counting files in staging folder."""
        await maildir_manager.ensure_directories()

        # Create some .mail files in staging
        staging_dir = tmp_path / ".staging"
        (staging_dir / "test1.mail").write_bytes(b"email1")
        (staging_dir / "test2.mail").write_bytes(b"email2")
        (staging_dir / "notmail.txt").write_bytes(b"ignored")

        count = await maildir_manager.count_staging()
        assert count == 2

    @pytest.mark.asyncio
    async def test_count_staging_empty_folder(self, maildir_manager, tmp_path: Path) -> None:
        """Test counting files in empty staging folder."""
        await maildir_manager.ensure_directories()

        count = await maildir_manager.count_staging()
        assert count == 0

    @pytest.mark.asyncio
    async def test_count_staging_nonexistent_folder(self, maildir_manager) -> None:
        """Test counting files when staging folder doesn't exist."""
        count = await maildir_manager.count_staging()
        assert count == 0

    @pytest.mark.asyncio
    async def test_count_failed_with_files(self, maildir_manager, tmp_path: Path) -> None:
        """Test counting files in failed folder."""
        await maildir_manager.ensure_directories()

        # Create some .mail files in .failed
        failed_dir = tmp_path / ".staging" / ".failed"
        (failed_dir / "failed1.mail").write_bytes(b"email1")
        (failed_dir / "failed2.mail").write_bytes(b"email2")
        (failed_dir / "failed3.mail").write_bytes(b"email3")

        count = await maildir_manager.count_failed()
        assert count == 3

    @pytest.mark.asyncio
    async def test_count_failed_empty_folder(self, maildir_manager, tmp_path: Path) -> None:
        """Test counting files in empty failed folder."""
        await maildir_manager.ensure_directories()

        count = await maildir_manager.count_failed()
        assert count == 0

    @pytest.mark.asyncio
    async def test_count_failed_nonexistent_folder(self, maildir_manager) -> None:
        """Test counting files when failed folder doesn't exist."""
        count = await maildir_manager.count_failed()
        assert count == 0


# ==============================================================================
# LMTPDelivery Tests
# ==============================================================================


class TestLMTPDelivery:
    """Tests for LMTPDelivery class."""

    @pytest.fixture
    def mock_lmtp_settings(self) -> MagicMock:
        """Create mock settings for LMTPDelivery."""
        settings = MagicMock()
        settings.lmtp_host = "localhost"
        settings.lmtp_port = 24
        settings.mail_user = "testuser"
        return settings

    @pytest.fixture
    def lmtp_client(self, mock_lmtp_settings: MagicMock):
        """Create LMTPDelivery instance."""
        from postal_inspector.transport.lmtp_client import LMTPDelivery

        return LMTPDelivery(mock_lmtp_settings)

    def test_init_sets_config_correctly(self, mock_lmtp_settings: MagicMock) -> None:
        """Test that LMTPDelivery initializes with correct settings."""
        from postal_inspector.transport.lmtp_client import LMTPDelivery

        client = LMTPDelivery(mock_lmtp_settings)

        assert client.host == "localhost"
        assert client.port == 24
        assert client.recipient == "testuser"

    @pytest.mark.asyncio
    async def test_deliver_success(self, lmtp_client) -> None:
        """Test successful email delivery."""
        with patch("postal_inspector.transport.lmtp_client.aiosmtplib") as mock_smtp:
            # Mock successful SMTP connection and sendmail
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.sendmail = AsyncMock()
            mock_smtp.SMTP.return_value = mock_client

            raw_email = b"From: test@example.com\nSubject: Test\n\nBody"
            result = await lmtp_client.deliver(raw_email)

            assert result is True
            mock_client.sendmail.assert_called_once_with(
                "",  # Empty envelope sender
                ["testuser"],
                raw_email,
            )

    @pytest.mark.asyncio
    async def test_deliver_uses_empty_envelope_sender(self, lmtp_client) -> None:
        """Test that delivery uses empty envelope sender (MAIL FROM:<>)."""
        with patch("postal_inspector.transport.lmtp_client.aiosmtplib") as mock_smtp:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.sendmail = AsyncMock()
            mock_smtp.SMTP.return_value = mock_client

            await lmtp_client.deliver(b"email content")

            # First argument to sendmail should be empty string
            call_args = mock_client.sendmail.call_args
            assert call_args[0][0] == ""

    @pytest.mark.asyncio
    async def test_deliver_permanent_failure_raises_delivery_error(self, lmtp_client) -> None:
        """Test that 5xx errors raise DeliveryError."""
        import aiosmtplib

        with patch("postal_inspector.transport.lmtp_client.aiosmtplib") as mock_smtp:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            # Simulate 550 permanent failure
            mock_client.sendmail = AsyncMock(
                side_effect=aiosmtplib.SMTPResponseException(550, "User not found")
            )
            mock_smtp.SMTP.return_value = mock_client
            mock_smtp.SMTPResponseException = aiosmtplib.SMTPResponseException

            with pytest.raises(DeliveryError) as exc_info:
                await lmtp_client.deliver(b"email")

            assert "permanent failure" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_deliver_temporary_failure_returns_false(self, lmtp_client) -> None:
        """Test that 4xx errors return False (can retry)."""
        import aiosmtplib

        with patch("postal_inspector.transport.lmtp_client.aiosmtplib") as mock_smtp:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            # Simulate 451 temporary failure
            mock_client.sendmail = AsyncMock(
                side_effect=aiosmtplib.SMTPResponseException(451, "Try again later")
            )
            mock_smtp.SMTP.return_value = mock_client
            mock_smtp.SMTPResponseException = aiosmtplib.SMTPResponseException

            result = await lmtp_client.deliver(b"email")

            assert result is False

    @pytest.mark.asyncio
    async def test_deliver_connection_error_returns_false(self, lmtp_client) -> None:
        """Test that connection errors return False."""
        import aiosmtplib

        with patch.object(aiosmtplib, "SMTP", autospec=True) as mock_smtp_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(
                side_effect=ConnectionRefusedError("Connection refused")
            )
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_smtp_class.return_value = mock_client

            result = await lmtp_client.deliver(b"email")

            assert result is False

    @pytest.mark.asyncio
    async def test_deliver_timeout_error_returns_false(self, lmtp_client) -> None:
        """Test that timeout errors return False."""

        import aiosmtplib

        with patch.object(aiosmtplib, "SMTP", autospec=True) as mock_smtp_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(side_effect=TimeoutError("Connection timed out"))
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_smtp_class.return_value = mock_client

            result = await lmtp_client.deliver(b"email")

            assert result is False

    @pytest.mark.asyncio
    async def test_check_connection_success(self, lmtp_client) -> None:
        """Test successful connection check."""
        with patch("postal_inspector.transport.lmtp_client.aiosmtplib") as mock_smtp:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_smtp.SMTP.return_value = mock_client

            result = await lmtp_client.check_connection()

            assert result is True

    @pytest.mark.asyncio
    async def test_check_connection_failure(self, lmtp_client) -> None:
        """Test failed connection check."""
        with patch("postal_inspector.transport.lmtp_client.aiosmtplib") as mock_smtp:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(
                side_effect=ConnectionRefusedError("Connection refused")
            )
            mock_smtp.SMTP.return_value = mock_client

            result = await lmtp_client.check_connection()

            assert result is False

    @pytest.mark.asyncio
    async def test_deliver_smtp_configuration(self, lmtp_client) -> None:
        """Test that SMTP is configured correctly for LMTP."""
        with patch("postal_inspector.transport.lmtp_client.aiosmtplib") as mock_smtp:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.sendmail = AsyncMock()
            mock_smtp.SMTP.return_value = mock_client

            await lmtp_client.deliver(b"email")

            # Verify SMTP was initialized with correct parameters
            mock_smtp.SMTP.assert_called_once_with(
                hostname="localhost",
                port=24,
                use_tls=False,
                timeout=10,
            )


# ==============================================================================
# IMAPFetcher Tests
# ==============================================================================


class TestIMAPFetcher:
    """Tests for IMAPFetcher class."""

    @pytest.fixture
    def mock_imap_settings(self) -> MagicMock:
        """Create mock settings for IMAPFetcher."""
        settings = MagicMock()
        settings.upstream_server = "imap.example.com"
        settings.upstream_port = 993
        settings.upstream_user = "user@example.com"
        settings.upstream_pass.get_secret_value.return_value = "password123"
        return settings

    @pytest.fixture
    def imap_fetcher(self, mock_imap_settings: MagicMock):
        """Create IMAPFetcher instance."""
        from postal_inspector.transport.imap_client import IMAPFetcher

        return IMAPFetcher(mock_imap_settings)

    def test_init_sets_config_correctly(self, mock_imap_settings: MagicMock) -> None:
        """Test that IMAPFetcher initializes with correct settings."""
        from postal_inspector.transport.imap_client import IMAPFetcher

        fetcher = IMAPFetcher(mock_imap_settings)

        assert fetcher.host == "imap.example.com"
        assert fetcher.port == 993
        assert fetcher.user == "user@example.com"
        assert fetcher.password == "password123"
        assert fetcher._client is None

    @pytest.mark.asyncio
    async def test_connect_success(self, imap_fetcher) -> None:
        """Test successful IMAP connection."""
        with patch("postal_inspector.transport.imap_client.aioimaplib") as mock_imap:
            mock_client = AsyncMock()
            mock_client.wait_hello_from_server = AsyncMock()
            mock_client.login = AsyncMock()
            mock_imap.IMAP4_SSL.return_value = mock_client

            await imap_fetcher.connect()

            assert imap_fetcher._client is mock_client
            mock_imap.IMAP4_SSL.assert_called_once_with(
                host="imap.example.com", port=993, timeout=30
            )
            mock_client.wait_hello_from_server.assert_called_once()
            mock_client.login.assert_called_once_with("user@example.com", "password123")

    @pytest.mark.asyncio
    async def test_connect_failure_raises_delivery_error(self, imap_fetcher) -> None:
        """Test that connection failure raises DeliveryError."""
        with patch("postal_inspector.transport.imap_client.aioimaplib") as mock_imap:
            mock_client = AsyncMock()
            mock_client.wait_hello_from_server = AsyncMock(
                side_effect=Exception("Connection timeout")
            )
            mock_imap.IMAP4_SSL.return_value = mock_client

            with pytest.raises(DeliveryError) as exc_info:
                await imap_fetcher.connect()

            assert "IMAP connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_login_failure_raises_delivery_error(self, imap_fetcher) -> None:
        """Test that login failure raises DeliveryError."""
        with patch("postal_inspector.transport.imap_client.aioimaplib") as mock_imap:
            mock_client = AsyncMock()
            mock_client.wait_hello_from_server = AsyncMock()
            mock_client.login = AsyncMock(side_effect=Exception("Invalid credentials"))
            mock_imap.IMAP4_SSL.return_value = mock_client

            with pytest.raises(DeliveryError) as exc_info:
                await imap_fetcher.connect()

            assert "IMAP connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_disconnect_with_client(self, imap_fetcher) -> None:
        """Test disconnecting when client exists."""
        mock_client = AsyncMock()
        mock_client.logout = AsyncMock()
        imap_fetcher._client = mock_client

        await imap_fetcher.disconnect()

        mock_client.logout.assert_called_once()
        assert imap_fetcher._client is None

    @pytest.mark.asyncio
    async def test_disconnect_without_client(self, imap_fetcher) -> None:
        """Test disconnecting when no client exists."""
        imap_fetcher._client = None

        # Should not raise
        await imap_fetcher.disconnect()

        assert imap_fetcher._client is None

    @pytest.mark.asyncio
    async def test_disconnect_suppresses_logout_errors(self, imap_fetcher) -> None:
        """Test that disconnect suppresses errors during logout."""
        mock_client = AsyncMock()
        mock_client.logout = AsyncMock(side_effect=Exception("Logout failed"))
        imap_fetcher._client = mock_client

        # Should not raise
        await imap_fetcher.disconnect()

        assert imap_fetcher._client is None

    @pytest.mark.asyncio
    async def test_fetch_new_messages_not_connected(self, imap_fetcher) -> None:
        """Test that fetch_new_messages raises error when not connected."""
        imap_fetcher._client = None

        with pytest.raises(DeliveryError) as exc_info:
            async for _ in imap_fetcher.fetch_new_messages():
                pass

        assert "IMAP not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_new_messages_success(self, imap_fetcher) -> None:
        """Test successfully fetching new messages."""
        mock_client = AsyncMock()
        mock_client.select = AsyncMock()
        mock_client.search = AsyncMock(return_value=("OK", [b"1 2 3"]))
        # Mock fetch to return email data
        mock_client.fetch = AsyncMock(
            side_effect=[
                ("OK", [(b"1 RFC822", b"email content 1")]),
                ("OK", [(b"2 RFC822", b"email content 2")]),
                ("OK", [(b"3 RFC822", b"email content 3")]),
            ]
        )
        imap_fetcher._client = mock_client

        messages = []
        async for msg in imap_fetcher.fetch_new_messages():
            messages.append(msg)

        assert len(messages) == 3
        assert messages[0] == b"email content 1"
        assert messages[1] == b"email content 2"
        assert messages[2] == b"email content 3"

    @pytest.mark.asyncio
    async def test_fetch_new_messages_no_messages(self, imap_fetcher) -> None:
        """Test fetching when there are no new messages."""
        mock_client = AsyncMock()
        mock_client.select = AsyncMock()
        mock_client.search = AsyncMock(return_value=("OK", [b""]))
        imap_fetcher._client = mock_client

        messages = []
        async for msg in imap_fetcher.fetch_new_messages():
            messages.append(msg)

        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_fetch_new_messages_search_failure(self, imap_fetcher) -> None:
        """Test that search failure returns early."""
        mock_client = AsyncMock()
        mock_client.select = AsyncMock()
        mock_client.search = AsyncMock(return_value=("NO", []))
        imap_fetcher._client = mock_client

        messages = []
        async for msg in imap_fetcher.fetch_new_messages():
            messages.append(msg)

        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_fetch_new_messages_fetch_failure_continues(self, imap_fetcher) -> None:
        """Test that fetch failure for one message continues to next."""
        mock_client = AsyncMock()
        mock_client.select = AsyncMock()
        mock_client.search = AsyncMock(return_value=("OK", [b"1 2"]))
        # First fetch fails, second succeeds
        mock_client.fetch = AsyncMock(
            side_effect=[
                Exception("Fetch failed"),
                ("OK", [(b"2 RFC822", b"email content 2")]),
            ]
        )
        imap_fetcher._client = mock_client

        messages = []
        async for msg in imap_fetcher.fetch_new_messages():
            messages.append(msg)

        # Should get second message despite first failing
        assert len(messages) == 1
        assert messages[0] == b"email content 2"

    @pytest.mark.asyncio
    async def test_fetch_new_messages_fetch_not_ok(self, imap_fetcher) -> None:
        """Test handling of non-OK fetch response."""
        mock_client = AsyncMock()
        mock_client.select = AsyncMock()
        mock_client.search = AsyncMock(return_value=("OK", [b"1"]))
        mock_client.fetch = AsyncMock(return_value=("NO", []))
        imap_fetcher._client = mock_client

        messages = []
        async for msg in imap_fetcher.fetch_new_messages():
            messages.append(msg)

        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_context_manager_enter(self, imap_fetcher) -> None:
        """Test async context manager __aenter__."""
        with patch("postal_inspector.transport.imap_client.aioimaplib") as mock_imap:
            mock_client = AsyncMock()
            mock_client.wait_hello_from_server = AsyncMock()
            mock_client.login = AsyncMock()
            mock_imap.IMAP4_SSL.return_value = mock_client

            result = await imap_fetcher.__aenter__()

            assert result is imap_fetcher
            assert imap_fetcher._client is mock_client

    @pytest.mark.asyncio
    async def test_context_manager_exit(self, imap_fetcher) -> None:
        """Test async context manager __aexit__."""
        mock_client = AsyncMock()
        mock_client.logout = AsyncMock()
        imap_fetcher._client = mock_client

        await imap_fetcher.__aexit__(None, None, None)

        mock_client.logout.assert_called_once()
        assert imap_fetcher._client is None

    @pytest.mark.asyncio
    async def test_context_manager_full_usage(self, mock_imap_settings) -> None:
        """Test using IMAPFetcher as async context manager."""
        from postal_inspector.transport.imap_client import IMAPFetcher

        with patch("postal_inspector.transport.imap_client.aioimaplib") as mock_imap:
            mock_client = AsyncMock()
            mock_client.wait_hello_from_server = AsyncMock()
            mock_client.login = AsyncMock()
            mock_client.logout = AsyncMock()
            mock_client.select = AsyncMock()
            mock_client.search = AsyncMock(return_value=("OK", [b""]))
            mock_imap.IMAP4_SSL.return_value = mock_client

            async with IMAPFetcher(mock_imap_settings) as fetcher:
                messages = [msg async for msg in fetcher.fetch_new_messages()]

            # Verify connection lifecycle
            mock_client.wait_hello_from_server.assert_called_once()
            mock_client.login.assert_called_once()
            mock_client.logout.assert_called_once()
            assert messages == []

    @pytest.mark.asyncio
    async def test_fetch_selects_inbox(self, imap_fetcher) -> None:
        """Test that fetch_new_messages selects INBOX folder."""
        mock_client = AsyncMock()
        mock_client.select = AsyncMock()
        mock_client.search = AsyncMock(return_value=("OK", [b""]))
        imap_fetcher._client = mock_client

        async for _ in imap_fetcher.fetch_new_messages():
            pass

        mock_client.select.assert_called_once_with("INBOX")

    @pytest.mark.asyncio
    async def test_fetch_searches_unseen(self, imap_fetcher) -> None:
        """Test that fetch_new_messages searches for UNSEEN messages."""
        mock_client = AsyncMock()
        mock_client.select = AsyncMock()
        mock_client.search = AsyncMock(return_value=("OK", [b""]))
        imap_fetcher._client = mock_client

        async for _ in imap_fetcher.fetch_new_messages():
            pass

        mock_client.search.assert_called_once_with("UNSEEN")


# ==============================================================================
# Integration-style Tests (still mocked, but test module interactions)
# ==============================================================================


class TestTransportIntegration:
    """Integration-style tests for transport modules working together."""

    @pytest.fixture
    def mock_settings(self, tmp_path: Path) -> MagicMock:
        """Create comprehensive mock settings."""
        settings = MagicMock()
        # Maildir settings
        settings.maildir_path = str(tmp_path)
        settings.mail_user = "testuser"
        # LMTP settings
        settings.lmtp_host = "localhost"
        settings.lmtp_port = 24
        # IMAP settings
        settings.upstream_server = "imap.example.com"
        settings.upstream_port = 993
        settings.upstream_user = "user@example.com"
        settings.upstream_pass.get_secret_value.return_value = "password"
        return settings

    @pytest.mark.asyncio
    async def test_delivery_workflow(self, mock_settings: MagicMock) -> None:
        """Test typical email delivery workflow: fetch -> deliver -> archive."""
        from postal_inspector.transport.lmtp_client import LMTPDelivery
        from postal_inspector.transport.maildir import MaildirManager

        # Create managers
        maildir = MaildirManager(mock_settings)
        lmtp = LMTPDelivery(mock_settings)

        # Ensure directories
        await maildir.ensure_directories()

        # Mock LMTP delivery
        with patch("postal_inspector.transport.lmtp_client.aiosmtplib") as mock_smtp:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.sendmail = AsyncMock()
            mock_smtp.SMTP.return_value = mock_client

            raw_email = b"From: test@example.com\nSubject: Test\n\nBody"

            # Deliver email
            result = await lmtp.deliver(raw_email)
            assert result is True

            # Archive delivered email
            filename = await maildir.archive_delivered(raw_email, "<msg-123>")
            assert filename != ""

    @pytest.mark.asyncio
    async def test_quarantine_workflow(self, mock_settings: MagicMock) -> None:
        """Test quarantine workflow for suspicious emails."""
        from postal_inspector.transport.maildir import MaildirManager

        maildir = MaildirManager(mock_settings)
        await maildir.ensure_directories()

        raw_email = b"From: phish@fake.com\nSubject: URGENT\n\nClick here"

        # Quarantine the email
        filename = await maildir.quarantine(raw_email, "Phishing detected")

        # Verify quarantined
        quarantine_path = (
            Path(mock_settings.maildir_path) / "testuser" / ".Quarantine" / "cur" / filename
        )
        assert quarantine_path.exists()
        assert quarantine_path.read_bytes() == raw_email

    @pytest.mark.asyncio
    async def test_failed_delivery_workflow(self, mock_settings: MagicMock) -> None:
        """Test workflow when delivery fails permanently."""
        import aiosmtplib

        from postal_inspector.transport.lmtp_client import LMTPDelivery
        from postal_inspector.transport.maildir import MaildirManager

        maildir = MaildirManager(mock_settings)
        lmtp = LMTPDelivery(mock_settings)

        await maildir.ensure_directories()

        # Mock LMTP permanent failure
        with patch("postal_inspector.transport.lmtp_client.aiosmtplib") as mock_smtp:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.sendmail = AsyncMock(
                side_effect=aiosmtplib.SMTPResponseException(550, "User unknown")
            )
            mock_smtp.SMTP.return_value = mock_client
            mock_smtp.SMTPResponseException = aiosmtplib.SMTPResponseException

            raw_email = b"From: test@example.com\nSubject: Test\n\nBody"

            # Attempt delivery - should raise
            with pytest.raises(DeliveryError):
                await lmtp.deliver(raw_email)

            # Move to failed folder
            filename = await maildir.move_to_failed(raw_email, "Permanent delivery failure")
            assert filename != ""

            # Verify in failed folder
            assert await maildir.count_failed() == 1
