# Postal Inspector - Project Rules

## Overview
AI-powered email security scanner built in Python. Fetches mail from upstream IMAP, scans with Claude using the Anthropic SDK, and delivers via LMTP to Dovecot.

## Architecture (Python Implementation)
- **Python async mail processor** (single service replaces mail-fetch + ai-scanner bash scripts)
- **Anthropic SDK** for AI scanning (direct API calls, not CLI pipes)
- **aioimaplib** for async IMAP fetching (replaces fetchmail)
- **aiosmtplib** for async LMTP delivery (replaces netcat)
- **uv** for package management
- **Fail-closed security**: Default to QUARANTINE on any error
- **Retain-by-default**: Archive emails, never delete

### Email Flow
```
IMAPFetcher → MailProcessor → AIAnalyzer → LMTPDelivery
                                  ↓
                            (QUARANTINE → Maildir)
```

## Code Standards
- Python 3.12+
- Type hints on all functions
- Pydantic for config validation
- structlog for logging (JSON in production)
- asyncio throughout
- ruff for linting/formatting
- mypy for type checking

## Key Patterns

### Security
```python
# Always fail-closed
try:
    verdict = await analyzer.scan(email)
except Exception:
    verdict = Verdict.QUARANTINE  # Never SAFE on error
```

### Rate Limiting
- Max 30 API calls per minute
- Use token bucket pattern

### Retry Logic
- Max 5 retries per email
- Exponential backoff (2s, 4s, 8s)
- After max retries → move to .failed/

## Directory Structure
```
src/postal_inspector/
├── __init__.py
├── __main__.py
├── cli.py
├── exceptions.py
├── config/
│   ├── __init__.py
│   └── settings.py
├── core/
│   ├── __init__.py
│   ├── logging.py
│   └── security.py
├── scanner/
│   ├── __init__.py
│   ├── verdict.py
│   ├── prompts.py
│   └── ai_analyzer.py
├── transport/
│   ├── __init__.py
│   ├── imap_client.py
│   ├── lmtp_client.py
│   └── maildir.py
├── briefing/
│   ├── __init__.py
│   ├── health.py
│   └── generator.py
├── services/
│   ├── __init__.py
│   ├── mail_processor.py
│   └── scheduler.py
└── models/
    ├── __init__.py
    └── email.py
```

## Environment Variables
- `ANTHROPIC_API_KEY` - Required for AI scanning
- `MAIL_USER` - Local mailbox user
- `UPSTREAM_SERVER` - IMAP server to fetch from
- `UPSTREAM_USER` / `UPSTREAM_PASS` - IMAP credentials
- `LMTP_HOST` / `LMTP_PORT` - Dovecot LMTP endpoint

## Commands

### Development
```bash
make dev          # Install with dev dependencies
make test         # Run unit tests
make lint         # Run ruff linter
make type-check   # Run mypy
make check        # Run all checks
```

### Docker
```bash
make build        # Build containers
make up           # Start services
make down         # Stop services
make logs         # View logs
```

### CLI
```bash
postal-inspector scanner           # Run mail processor
postal-inspector briefing --now    # Generate briefing immediately
postal-inspector briefing --schedule  # Run scheduler
postal-inspector health            # Check system health
```

## Docker
- All services run as vmail (uid 5000)
- Use uv in containers (fast installs)
- Health checks required on all services
