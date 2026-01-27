"""AI-powered daily email briefing generator."""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles
import aiofiles.os
import anthropic
import structlog
from anthropic.types import TextBlock

from postal_inspector.briefing.health import HealthChecker
from postal_inspector.models import ParsedEmail
from postal_inspector.transport.maildir import MaildirManager

if TYPE_CHECKING:
    from postal_inspector.config import Settings

logger = structlog.get_logger(__name__)

# HTML sanitization pattern - remove dangerous elements
DANGEROUS_PATTERNS = [
    (r"<script[^>]*>.*?</script>", "", re.IGNORECASE | re.DOTALL),
    (r"<style[^>]*>.*?</style>", "", re.IGNORECASE | re.DOTALL),
    (r'on\w+\s*=\s*["\'][^"\']*["\']', "", re.IGNORECASE),
    (r"javascript:", "", re.IGNORECASE),
    (r"<iframe[^>]*>.*?</iframe>", "", re.IGNORECASE | re.DOTALL),
    (r"<object[^>]*>.*?</object>", "", re.IGNORECASE | re.DOTALL),
    (r"<embed[^>]*>", "", re.IGNORECASE),
    (r"<form[^>]*>.*?</form>", "", re.IGNORECASE | re.DOTALL),
]


def sanitize_html(html: str) -> str:
    """Remove dangerous HTML elements."""
    for pattern, replacement, flags in DANGEROUS_PATTERNS:
        html = re.sub(pattern, replacement, html, flags=flags)
    return html


BRIEFING_PROMPT = """Generate an HTML email briefing summarizing these emails from the last 24 hours.

RULES:
1. Output ONLY clean HTML - no markdown, no code blocks
2. NO script tags, NO event handlers (onclick, etc), NO iframes
3. Use inline CSS only
4. Categories: Action Items, Personal, Business, Newsletters, Quarantined
5. Be conversational ("Eric wants to meet" not "Meeting request from Eric")
6. Keep it concise - summarize, don't list everything

EMAILS:
{email_summaries}

Generate the HTML briefing now:"""


class BriefingGenerator:
    """Generate AI-powered daily email briefings."""

    def __init__(self, settings: "Settings"):
        self.settings = settings
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value()
        )
        self.maildir = MaildirManager(settings)
        self.health_checker = HealthChecker(settings)
        self.maildir_path = Path(settings.maildir_path) / settings.mail_user

    async def generate(self) -> str:
        """Generate complete HTML briefing."""
        logger.info("generating_briefing")

        # Collect recent emails
        emails = await self._collect_recent_emails()

        # Generate health report
        health = await self.health_checker.check_all()
        health_html = health.to_html()

        # Generate AI summary
        if emails:
            email_summaries = self._format_emails_for_prompt(emails)
            summary_html = await self._generate_ai_summary(email_summaries)
        else:
            summary_html = "<p>No new emails in the last 24 hours.</p>"

        # Combine into final briefing
        date_str = datetime.now().strftime("%A, %B %d")
        return self._render_briefing(date_str, health_html, summary_html)

    async def _collect_recent_emails(self) -> list[ParsedEmail]:
        """Collect emails from last 24 hours."""
        cutoff = datetime.now() - timedelta(hours=24)
        cutoff_ts = cutoff.timestamp()

        emails = []
        folders = ["cur", "new", ".Sent/cur", ".Quarantine/cur"]

        for folder in folders:
            folder_path = self.maildir_path / folder
            if not await aiofiles.os.path.exists(folder_path):
                continue

            try:
                for filename in await aiofiles.os.listdir(folder_path):
                    file_path = folder_path / filename
                    try:
                        stat = await aiofiles.os.stat(file_path)
                        if stat.st_mtime >= cutoff_ts:
                            async with aiofiles.open(file_path, "rb") as f:
                                raw = await f.read()
                            email = ParsedEmail.parse(raw)
                            emails.append(email)
                    except Exception as e:
                        logger.warning("email_read_error", file=str(file_path), error=str(e))
            except Exception as e:
                logger.warning("folder_scan_error", folder=folder, error=str(e))

        logger.info("emails_collected", count=len(emails))
        return emails

    def _format_emails_for_prompt(self, emails: list[ParsedEmail]) -> str:
        """Format emails for AI prompt."""
        summaries = []
        for email in emails[:50]:  # Limit to 50 emails
            summaries.append(
                f"FROM: {email.from_addr[:100]}\n"
                f"SUBJECT: {email.subject[:100]}\n"
                f"PREVIEW: {email.body_preview[:200]}\n"
            )
        return "\n---\n".join(summaries)

    async def _generate_ai_summary(self, email_summaries: str) -> str:
        """Generate AI summary of emails."""
        prompt = BRIEFING_PROMPT.format(email_summaries=email_summaries)

        try:
            response = await self.client.messages.create(
                model=self.settings.anthropic_model,
                max_tokens=2000,
                timeout=120,
                messages=[{"role": "user", "content": prompt}],
            )
            content_block = response.content[0]
            if isinstance(content_block, TextBlock):
                html = content_block.text.strip()
                return sanitize_html(html)
            raise ValueError(f"Unexpected content type: {type(content_block)}")
        except Exception as e:
            logger.error("ai_briefing_failed", error=str(e))
            return f"<p>Failed to generate AI summary: {str(e)[:50]}</p>"

    def _render_briefing(self, date: str, health_html: str, summary_html: str) -> str:
        """Render final briefing HTML."""
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Security-Policy" content="script-src 'none';">
    <title>Daily Briefing - {date}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
             max-width: 600px; margin: 0 auto; padding: 20px; background: #f5f5f5;">
    <div style="background: white; padding: 30px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
        <h1 style="margin: 0 0 20px 0; color: #333;">&#128236; Your Daily Briefing</h1>
        <p style="color: #666; margin-bottom: 20px;">{date}</p>

        {health_html}

        <div style="margin-top: 20px;">
            {summary_html}
        </div>

        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
        <p style="color: #999; font-size: 12px; text-align: center;">
            Generated by Postal Inspector
        </p>
    </div>
</body>
</html>"""

    async def deliver_briefing(self, html: str) -> bool:
        """Deliver briefing to inbox."""
        from postal_inspector.transport.lmtp_client import LMTPDelivery

        # Create MIME message
        date_str = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")
        message = f"""From: Daily Briefing <briefing@{self.settings.mail_domain}>
To: {self.settings.mail_user}@{self.settings.mail_domain}
Subject: Your Daily Briefing - {datetime.now().strftime("%A, %B %d")}
Date: {date_str}
MIME-Version: 1.0
Content-Type: text/html; charset=UTF-8

{html}"""

        lmtp = LMTPDelivery(self.settings)
        return await lmtp.deliver(message.encode("utf-8"))
