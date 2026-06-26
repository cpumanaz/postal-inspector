"""Async LMTP client for local delivery to Dovecot.

This module provides an async LMTP client that delivers scanned emails
to the local Dovecot server. It matches the behavior of the bash
deliver_via_lmtp() function in mail-scanner.sh.
"""

from typing import TYPE_CHECKING

import aiosmtplib
import structlog

from postal_inspector.exceptions import DeliveryError

if TYPE_CHECKING:
    from postal_inspector.config import Settings

logger = structlog.get_logger(__name__)


class LMTPDelivery:
    """Async LMTP client for delivering emails to Dovecot.

    This class handles LMTP delivery to the local Dovecot server.
    It uses aiosmtplib for async SMTP/LMTP communication.

    Attributes:
        host: LMTP server hostname.
        port: LMTP server port.
        recipient: Email recipient address.
    """

    def __init__(self, settings: "Settings") -> None:
        """Initialize the LMTP client.

        Args:
            settings: Application settings containing LMTP configuration.
        """
        self.host = settings.lmtp_host
        self.port = settings.lmtp_port
        self.recipient = settings.mail_user

    async def deliver(self, raw_email: bytes, recipient_override: str | None = None) -> bool:
        """Deliver email via LMTP to Dovecot.

        Sends the raw email to Dovecot via LMTP protocol. The envelope
        sender is empty (matching the bash version's MAIL FROM:<>).

        Args:
            raw_email: The raw email message as bytes.
            recipient_override: Optional specific recipient address (e.g., "svc-github@domain").
                               If None, uses the default mail_user.

        Returns:
            True on successful delivery, False on temporary failure.

        Raises:
            DeliveryError: On permanent failure (5xx response codes).
        """
        recipient = recipient_override if recipient_override else self.recipient
        logger.info("lmtp_delivering", host=self.host, port=self.port, recipient=recipient)

        try:
            # Connect to LMTP server (Dovecot on port 24)
            logger.info("lmtp_step_1_connecting", host=self.host, port=self.port)
            client = aiosmtplib.SMTP(
                hostname=self.host,
                port=self.port,
                use_tls=False,
                start_tls=False,
                timeout=10,
            )
            await client.connect()
            logger.info("lmtp_step_2_connected")

            # Send LHLO for LMTP protocol
            logger.info("lmtp_step_3_sending_lhlo", hostname=self.host)
            code, message = await client.execute_command(b"LHLO", self.host.encode())
            logger.info("lmtp_step_4_lhlo_response", code=code, message=str(message))
            if code not in (220, 250):
                raise DeliveryError(f"LHLO failed: {code} {message}")

            # Manually send LMTP commands instead of using sendmail()
            # MAIL FROM:<> (empty sender for bounce messages)
            logger.info("lmtp_step_5_mail_from")
            code, message = await client.execute_command(b"MAIL FROM:<>")
            logger.info("lmtp_step_6_mail_from_response", code=code, message=str(message))
            if code != 250:
                raise DeliveryError(f"MAIL FROM failed: {code} {message}")

            # RCPT TO:<user>
            logger.info("lmtp_step_7_rcpt_to", recipient=recipient)
            code, message = await client.execute_command(f"RCPT TO:<{recipient}>".encode())
            logger.info("lmtp_step_8_rcpt_to_response", code=code, message=str(message))
            if code not in (250, 251):
                raise DeliveryError(f"RCPT TO failed: {code} {message}")

            # DATA
            logger.info("lmtp_step_9_data")
            code, message = await client.execute_command(b"DATA")
            logger.info("lmtp_step_10_data_response", code=code, message=str(message))
            if code != 354:
                raise DeliveryError(f"DATA failed: {code} {message}")

            # Send email content followed by <CR><LF>.<CR><LF>
            logger.info("lmtp_step_11_sending_content", size=len(raw_email))

            # Access the underlying transport and send data directly
            # Ensure email ends with CRLF before the terminator
            if not raw_email.endswith(b"\r\n"):
                email_data = raw_email + b"\r\n.\r\n"
            else:
                email_data = raw_email + b".\r\n"

            # Write directly to the socket
            transport = client.transport
            transport.write(email_data)

            # Read the response - use execute_command with empty string to just read
            logger.info("lmtp_step_12_reading_delivery_response")
            code, message = await client.protocol.read_response()
            logger.info("lmtp_step_13_delivery_response", code=code, message=message)
            if code not in (250, 251):
                raise DeliveryError(f"Message delivery failed: {code} {message}")

            logger.info("lmtp_step_14_delivery_success")

            # Delivery confirmed — close connection gracefully.
            # quit() can fail after raw transport.write() desynchronizes
            # the aiosmtplib state machine, but the email is already saved.
            try:
                await client.quit()
            except Exception:
                client.close()
            logger.info("lmtp_delivered", recipient=recipient)
            return True

        except aiosmtplib.SMTPResponseException as e:
            # Check response code for permanent vs temporary failure
            if e.code >= 500:
                # Permanent failure (5xx) - should not retry
                logger.error(
                    "lmtp_permanent_failure",
                    code=e.code,
                    message=str(e.message),
                )
                raise DeliveryError(f"LMTP permanent failure: {e.code} {e.message}") from e
            else:
                # Temporary failure (4xx) - can retry
                logger.warning(
                    "lmtp_temporary_failure",
                    code=e.code,
                    message=str(e.message),
                )
                return False

        except Exception as e:
            logger.error("lmtp_error", error=str(e))
            return False

    async def check_connection(self) -> bool:
        """Test LMTP connectivity to Dovecot.

        Verifies TCP connectivity and server greeting. Does not send
        LHLO separately because aiosmtplib.connect() already performs
        an EHLO handshake which Dovecot LMTP accepts.

        Returns:
            True if connection is successful, False otherwise.
        """
        try:
            client = aiosmtplib.SMTP(
                hostname=self.host,
                port=self.port,
                use_tls=False,
                start_tls=False,
                timeout=5,
            )
            await client.connect()
            await client.quit()
            return True
        except Exception as e:
            logger.warning("lmtp_check_failed", error=str(e))
            return False
