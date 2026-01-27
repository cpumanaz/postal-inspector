"""Email data models for postal-inspector.

This module provides data classes for representing parsed email
messages throughout the application.
"""

import re
from dataclasses import dataclass
from email import message_from_bytes
from email.header import decode_header
from email.utils import parseaddr


@dataclass
class ParsedEmail:
    """A parsed email message with extracted headers and body preview.

    Attributes:
        message_id: The Message-ID header value.
        from_addr: The From header value.
        to_addr: The To header value.
        reply_to: The Reply-To header value (may be None).
        subject: The Subject header value.
        body_preview: First 800 characters of the text body.
        raw: The original raw email bytes.
    """

    message_id: str
    from_addr: str
    to_addr: str
    reply_to: str | None
    subject: str
    body_preview: str
    raw: bytes

    def get_recipient_address(self) -> str:
        """Extract the email address from the To header.

        Handles formats like:
        - "Name <email@domain.com>"
        - "<email@domain.com>"
        - "email@domain.com"

        Returns just the email address for use in LMTP RCPT TO.
        """
        # Use email.utils.parseaddr to properly extract email from header
        name, address = parseaddr(self.to_addr)
        return address if address else self.to_addr

    @classmethod
    def parse(cls, raw: bytes) -> "ParsedEmail":
        msg = message_from_bytes(raw)
        # Extract body preview (first 800 chars of text part)
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        body = payload.decode("utf-8", errors="ignore")[:800]
                    break
        else:
            payload = msg.get_payload(decode=True)
            if isinstance(payload, bytes):
                body = payload.decode("utf-8", errors="ignore")[:800]

        # Safely decode headers — handles RFC 2047 encoded words
        # and ensures we always get plain str (never email.header.Header)
        def _decode_header(val: object) -> str:
            if val is None:
                return ""
            try:
                parts = decode_header(str(val))
                decoded = []
                for fragment, charset in parts:
                    if isinstance(fragment, bytes):
                        decoded.append(
                            fragment.decode(charset or "utf-8", errors="replace")
                        )
                    else:
                        decoded.append(fragment)
                return " ".join(decoded)
            except Exception:
                return str(val)

        message_id = _decode_header(msg.get("Message-ID"))
        from_addr = _decode_header(msg.get("From"))
        to_addr = _decode_header(msg.get("To"))
        reply_to_raw = msg.get("Reply-To")
        reply_to = _decode_header(reply_to_raw) if reply_to_raw else None
        subject = _decode_header(msg.get("Subject"))

        return cls(
            message_id=message_id,
            from_addr=from_addr,
            to_addr=to_addr,
            reply_to=reply_to,
            subject=subject,
            body_preview=body.replace("\n", " ").strip(),
            raw=raw,
        )
