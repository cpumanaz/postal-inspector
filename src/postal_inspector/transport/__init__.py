"""Transport layer for postal-inspector.

This module provides async clients for email transport operations:
- IMAPFetcher: Fetch emails from upstream IMAP servers
- LMTPDelivery: Deliver emails to Dovecot via LMTP
- MaildirManager: Manage local maildir operations (archive, quarantine, failed)
"""

from postal_inspector.transport.imap_client import IMAPFetcher
from postal_inspector.transport.lmtp_client import LMTPDelivery
from postal_inspector.transport.maildir import MaildirManager

__all__ = ["IMAPFetcher", "LMTPDelivery", "MaildirManager"]
