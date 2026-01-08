# Mail Stack

**AI-powered self-hosted email server with intelligent threat detection and daily briefings.**

A privacy-focused email solution that pulls mail from any upstream IMAP provider into a local Dovecot server, with real-time AI analysis for phishing detection and daily AI-generated email summaries.

## Features

- **AI Security Scanner** - Real-time email analysis using Claude CLI to detect phishing, social engineering, and suspicious content
- **Daily AI Briefings** - Personalized HTML email summaries categorizing your inbox by priority
- **Privacy First** - Your email stays on your infrastructure, analyzed locally
- **Event-Driven** - Uses inotify for instant email processing, no polling delays
- **Virus Scanning** - ClamAV integration for attachment scanning
- **Security Hardened** - Defense-in-depth with read-only containers, dropped capabilities, input validation, and fail-closed design

## Architecture

```
                         INBOUND FLOW
┌─────────────────────────────────────────────────────────────────┐
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
│                    Dovecot IMAP (TLS only)                     │
│                           │                                     │
│                           ▼                                     │
│                     Mail Clients                                │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                       DAILY BRIEFING                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  8:00 AM ──► Scan last 24h ──► Claude AI ──► HTML Email        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Services

| Service | Description |
|---------|-------------|
| `imap` | Dovecot IMAP server (TLS on port 993) |
| `mail-fetch` | Fetchmail daemon pulling from upstream provider |
| `ai-scanner` | Claude CLI-powered threat detection (event-driven) |
| `daily-briefing` | AI-generated daily email summaries |
| `antivirus` | ClamAV virus scanning |

## Quick Start

See [GETTING-STARTED.md](GETTING-STARTED.md) for detailed setup instructions.

### Prerequisites

- Docker & Docker Compose
- [Claude CLI](https://github.com/anthropics/claude-code) authenticated on host
- TLS certificates for your mail domain
- Upstream IMAP provider credentials

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/mail-stack.git
cd mail-stack

# Configure environment
cp .env.example .env
nano .env  # Add your credentials

# Add TLS certificates
mkdir -p certs
cp /path/to/fullchain.pem certs/
cp /path/to/privkey.pem certs/

# Start the stack
make up

# Verify services
make status
```

### Mail Client Configuration

| Setting | Value |
|---------|-------|
| Server | `your.mail.server` |
| Port | `993` |
| Security | SSL/TLS |
| Username | Your `MAIL_USER` from `.env` |

**Note:** SMTP (sending) should use your upstream provider directly.

## Commands

```bash
make up            # Start all services
make down          # Stop all services
make restart       # Restart all services
make status        # Show service status
make logs          # Follow all logs
make logs-scanner  # Follow AI scanner logs
make logs-briefing # Follow daily briefing logs
make test-briefing # Generate a test briefing now
make backup        # Run manual backup
make build         # Rebuild all containers
make clean         # Stop and remove all containers
```

## AI Security Scanner

The scanner analyzes every incoming email in real-time using Claude. It detects:

- **Typosquatting** - `micros0ft.com`, `ourlook.com`, `amaz0n.com`
- **Header Mismatch** - From/Reply-To domain discrepancies
- **Urgency Tactics** - "Act now", "Account suspended", deadline pressure
- **Credential Harvesting** - Requests for passwords/personal info
- **Suspicious Attachments** - `.exe`, "patch", "update" in filenames
- **Prompt Injection** - Attempts to manipulate the AI analysis

Threats are automatically quarantined to the `Quarantine` folder.

### Security Model

The scanner uses a **fail-closed** design:
- If AI analysis fails repeatedly, emails are quarantined for manual review
- Strict output validation ensures only `SAFE|reason` or `QUARANTINE|reason` responses are accepted
- Rate limiting prevents abuse (30 scans/minute)

### Example Output

```
[2024-01-15 09:23:45] NEW: Subject: Urgent: Your account has been suspended
[2024-01-15 09:23:47]   -> QUARANTINE | Urgency and credential request
[2024-01-15 09:23:47]   ACTION: Moving to Quarantine
```

## Daily Briefing

Every morning (configurable hour), Claude generates a personalized HTML email summarizing your inbox:

- **Action Items** - Meetings, deadlines, requests needing response (red/orange)
- **Personal** - Emails from family/friends (blue)
- **Business** - Work correspondence, invoices (green)
- **Newsletters** - Grouped by source (purple)
- **Quarantined** - Brief mention of blocked threats (gray)

The briefing is delivered directly to your inbox as a beautifully formatted HTML email with Content-Security-Policy headers.

## Security Hardening

This project implements defense-in-depth security:

### Container Security
- `no-new-privileges` - Prevents privilege escalation
- `cap_drop: ALL` - Drops all Linux capabilities
- Resource limits on all containers (memory, CPU, PIDs)
- Non-root execution using supercronic for scheduled tasks
- Docker's default seccomp profile blocks dangerous syscalls

### Input Validation
- All environment variables validated with strict regex patterns
- `MAIL_USER` restricted to `[a-zA-Z0-9_-]` to prevent path traversal
- Numeric fields validated (`UPSTREAM_PORT`, `FETCH_INTERVAL`, `BRIEFING_HOUR`)

### AI Security
- Emails treated as untrusted data in prompts
- Aggressive input sanitization removes control characters and injection markers
- Strict output validation - only exact format accepted
- HTML output sanitized to prevent XSS
- Rate limiting (30 scans/minute)
- Fail-closed on repeated AI failures

### Network Security
- Only TLS port 993 exposed (plaintext IMAP disabled)
- Claude credentials mounted read-only
- Auth socket restricted to vmail user (mode 0600)

## File Structure

```
mail-stack/
├── docker-compose.yml     # Service orchestration
├── Makefile               # Management commands
├── .env                   # Configuration (gitignored)
├── .env.example           # Configuration template
├── GETTING-STARTED.md     # Detailed setup guide
├── services/
│   ├── imap/              # Dovecot IMAP server
│   ├── mail-fetch/        # Fetchmail configuration
│   ├── ai-scanner/        # Claude threat detection
│   └── daily-briefing/    # AI daily summaries
├── scripts/
│   ├── install.sh         # System installation script
│   └── backup.sh          # Backup script
├── data/
│   └── maildir/           # Mail storage (gitignored)
├── logs/                  # Service logs (gitignored)
└── certs/                 # TLS certificates (gitignored)
```

## Backup

Automatic daily backups can be configured via cron:

```bash
# Add to crontab
0 2 * * * /path/to/mail-stack/scripts/backup.sh
```

Backups are compressed tarballs of the maildir, with configurable retention (default: 3 days).

## Troubleshooting

### Services not starting?
```bash
make logs  # Check for errors
```

### Email not being fetched?
```bash
make logs-fetch  # Check fetchmail logs
```

### AI scanner not working?
```bash
# Verify Claude CLI is authenticated
docker-compose exec ai-scanner claude --version

# Check scanner logs
make logs-scanner
```

### Permissions issues?
All mail files must be owned by vmail (uid 5000). The services handle this automatically, but if you manually add files:
```bash
sudo chown -R 5000:5000 data/maildir/
```

## Requirements

- Docker 20.10+
- Docker Compose 2.0+
- Claude CLI with valid authentication (`~/.claude` directory)
- 1GB+ RAM (ClamAV requires ~512MB for virus signatures)
- TLS certificate for mail domain

## Cost Estimate

Mail Stack uses Claude API for AI analysis. Typical costs:

| Usage | Estimated Cost |
|-------|----------------|
| Per email scan | ~$0.001-0.01 |
| Daily briefing | ~$0.01-0.05 |
| 100 emails/day | ~$1-3/month |

Costs vary based on email length and Claude API pricing. The scanner uses efficient prompts to minimize token usage.

## License

MIT

---

*Built with Claude AI for intelligent email management.*
