"""Logging configuration for postal-inspector.

This module provides structlog configuration and utility functions
for sanitizing log output.
"""

import logging
import re
from typing import Any

import structlog


def sanitize_for_log(text: str, max_length: int = 100) -> str:
    """Remove control characters and limit length for safe logging.

    Args:
        text: The text to sanitize.
        max_length: Maximum length of returned string.

    Returns:
        Sanitized text safe for logging.
    """
    if not text:
        return ""
    # Remove control chars and ANSI codes
    text = re.sub(r"[\x00-\x1f\x7f]", "", text)
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    return text[:max_length]


def configure_logging(json_format: bool = False, debug: bool = False) -> None:
    """Configure structlog for the application.

    Args:
        json_format: If True, output JSON logs (for production).
        debug: If True, enable DEBUG level logging.
    """
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
