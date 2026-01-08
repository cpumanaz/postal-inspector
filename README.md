# Mail Stack

**AI-powered self-hosted email server with intelligent threat detection and daily briefings.**

Tired of phishing emails slipping through? Want an AI assistant that reads your inbox and tells you what matters? Mail Stack pulls mail from your existing provider (Gmail, O365, Fastmail, etc.) into your own secure server, where Claude AI scans every message for threats and sends you a personalized daily summary.

## Why Mail Stack?

- **Your email, your server** - No third-party scanning your messages
- **AI catches what spam filters miss** - Typosquatting, social engineering, credential harvesting
- **Start your day informed** - Beautiful HTML briefing categorizing what needs attention
- **Simple Docker deployment** - One `make up` and you're running

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                         INBOUND FLOW                            │
│                                                                 │
│  Upstream IMAP ──► Fetchmail ──► AI Scanner                    │
│  (Gmail, O365,              │           │                       │
│   Fastmail...)              ▼           ▼                       │
│                      [INBOX/new]  → [QUARANTINE] (threats)     │
│                           │              │                      │
│                           ▼              │                      │
│                      [INBOX/cur] ◄───────┘ (safe mail)         │
│                           │                                     │
│                           ▼                                     │
│                    Dovecot IMAP ──► Your Mail Client           │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                       DAILY BRIEFING                            │
│                                                                 │
│  8:00 AM ──► Scan last 24h ──► Claude AI ──► HTML Email        │
└─────────────────────────────────────────────────────────────────┘
```

## Features

| Feature | Description |
|---------|-------------|
| **AI Security Scanner** | Real-time phishing detection using Claude |
| **Daily Briefings** | Personalized HTML summaries by priority |
| **Virus Scanning** | ClamAV attachment scanning |
| **Event-Driven** | Instant processing via inotify, no polling |
| **Security Hardened** | Dropped capabilities, resource limits, fail-closed design |

### What the Scanner Catches

- Typosquatting domains (`micros0ft.com`, `amaz0n.com`)
- Header mismatches (From ≠ Reply-To domain)
- Urgency tactics ("Act now!", "Account suspended")
- Credential harvesting attempts
- Suspicious attachments
- Prompt injection attacks

### Daily Briefing Categories

- **Action Items** - Meetings, deadlines, requests needing response
- **Personal** - Family and friends
- **Business** - Work correspondence, invoices
- **Newsletters** - Grouped by source
- **Quarantined** - Brief mention of blocked threats

## Quick Start

```bash
# Clone and configure
git clone https://github.com/yourusername/mail-stack.git
cd mail-stack
cp .env.example .env
nano .env  # Add your upstream IMAP credentials

# Add TLS certs (see GETTING-STARTED.md for details)
mkdir -p certs
cp /path/to/fullchain.pem certs/
cp /path/to/privkey.pem certs/

# Launch
make build && make up
make status  # Verify all services are healthy
```

**[Full Setup Guide →](GETTING-STARTED.md)**

## Tech Stack

| Component | Technology |
|-----------|------------|
| IMAP Server | Dovecot |
| Mail Fetcher | Fetchmail |
| AI Engine | Claude CLI |
| Virus Scanner | ClamAV |
| Scheduler | Supercronic |
| Container | Docker Compose |

## Commands

```bash
make up            # Start all services
make down          # Stop all services
make logs          # Follow all logs
make logs-scanner  # Watch AI scanner in action
make test-briefing # Generate a briefing now
make status        # Check service health
```

## Requirements

- Docker 20.10+ and Docker Compose 2.0+
- [Claude CLI](https://github.com/anthropics/claude-code) authenticated
- TLS certificate for your mail domain
- 1GB+ RAM (ClamAV needs ~512MB)
- Upstream IMAP provider (Gmail, O365, Fastmail, etc.)

## Cost

| Usage | Estimated Cost |
|-------|----------------|
| Per email scan | ~$0.001-0.01 |
| Daily briefing | ~$0.01-0.05 |
| 100 emails/day | ~$1-3/month |

## Documentation

- **[Getting Started](GETTING-STARTED.md)** - Full setup walkthrough
- **[Security Model](GETTING-STARTED.md#security-checklist)** - Defense-in-depth details

## License

MIT

---

*Built with Claude AI for intelligent email management.*
