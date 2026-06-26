# Postal Inspector

**AI-powered self-hosted email server with intelligent threat detection and daily briefings.**

Tired of phishing emails slipping through? Want an AI assistant that reads your inbox and tells you what matters? Postal Inspector pulls mail from your existing provider (Gmail, O365, Fastmail, etc.) into your own secure server, where Claude AI scans every message for threats and sends you a personalized daily summary.

## Why Postal Inspector?

### Smarter Threat Detection

Traditional spam filters use rules and blocklists. Postal Inspector verifies every message in **two layers**:

**1. Cryptographic authentication (deterministic).** It checks SPF/DKIM/DMARC alignment from the trustworthy `Authentication-Results` header. A forged "From" almost always fails DMARC, so spoofed senders are caught with certainty — not guesswork. (It keys on DKIM *alignment*, not SPF, so legitimately *forwarded* mail isn't false-flagged.)

**2. AI reasoning (Claude).** For authenticated mail, Claude actually *reads* and *reasons* about intent:

- "This email claims to be from Microsoft but the domain is `micros0ft.com`"
- "The sender says they're your CEO, but they're asking for gift cards via a Gmail address"
- "This 'invoice' attachment has an unusual filename pattern common in malware"

**Rule-based filters see patterns. Postal Inspector verifies identity, then understands intent.**

### Your Personal Email Assistant

Every morning, you get a briefing that took AI 2 minutes to write but saves you 20 minutes of inbox scanning:

- What needs a response today
- Who emailed that actually matters to you
- What got blocked and why

**Like having an executive assistant read your email first.**

### Privacy by Design

Your email stays on your infrastructure. No third-party cloud scanning your messages, no ad targeting, no selling your data. You control the server, the storage, and who has access.

## How It Works

```
┌──────────────────────────────────────────────────────────────────┐
│                         INBOUND FLOW                             │
│                                                                  │
│  Your Email ──────► Fetch ──────► Scan ──────► AI Scanner        │
│  (Gmail, O365,                                    │              │
│   Fastmail...)                          ┌────────┴────────┐      │
│                                         │                 │      │
│                                         ▼                 ▼      │
│                                      [SAFE]        [QUARANTINE]  │
│                                         │                        │
│                                         ▼                        │
│                                   Your Mail Server               │
│                                         │                        │
│                                         ▼                        │
│                                    Mail Client                   │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│                       DAILY BRIEFING                             │
│                                                                  │
│  Every morning ──► Review inbox ──► AI summary ──► Email to you  │
└──────────────────────────────────────────────────────────────────┘
```

Mail is scanned *before* it reaches your inbox, not after — first its sender authentication (DMARC/DKIM) is verified, then Claude analyzes the content. If the AI is uncertain or something fails, the email goes to Quarantine - never delivered by default. Suspicious mail can't slip through due to errors.

## Features

| Feature | Description |
|---------|-------------|
| **Sender Authentication** | DMARC/SPF/DKIM verified deterministically before content analysis — spoofing caught with certainty |
| **AI Security Scanner** | Authenticated mail analyzed for threats in real-time by Claude |
| **Daily Briefings** | Morning summary of what needs your attention |
| **Virus Scanning** | Attachments checked before delivery |
| **Instant Processing** | New mail scanned immediately, not on a schedule |
| **Secure by Default** | When in doubt, quarantine - nothing slips through |

### What the Scanner Catches

- Spoofed senders (failed DMARC/DKIM — the "From" is forged)
- Fake / look-alike domains (`micros0ft.com`, `amaz0n.com`)
- Sender address tricks (reply goes somewhere different than it appears)
- Urgency tactics ("Act now!", "Account suspended")
- Credential harvesting ("Verify your password")
- Suspicious attachments

### Daily Briefing Categories

- **Action Items** - Meetings, deadlines, requests needing response
- **Personal** - Family and friends
- **Business** - Work correspondence, invoices
- **Newsletters** - Grouped by source
- **Quarantined** - Brief mention of blocked threats

**[View Sample Briefing →](https://cpumanaz.github.io/postal-inspector/docs/sample-briefing.html)**

## Requirements

- Linux server with Docker 20.10+ and Docker Compose 2.0+ — *or* a Kubernetes cluster (see below)
- An [Anthropic API key](https://console.anthropic.com/) for AI scanning
- Domain name with DNS control
- TLS certificate for your mail domain
- 1GB+ RAM (ClamAV needs ~512MB)
- Upstream IMAP provider (Gmail, O365, Fastmail, etc.)

AI scanning uses the Anthropic API and is billed per token. For personal mail volume this is typically a few cents to a couple of dollars a month. The model is configurable via `ANTHROPIC_MODEL` (default: `claude-opus-4-8`).

## Get Started

**[Installation Guide → (Docker Compose)](docs/GETTING-STARTED.md)**

Running on Kubernetes? See **[kubernetes/README.md](kubernetes/README.md)** for a portable, host-agnostic kustomize deployment.

## Under the Hood

Built on proven open-source components: Dovecot (IMAP), ClamAV, and the Anthropic SDK. Scanning combines a deterministic DMARC/DKIM authentication gate with Claude content analysis — **fail-closed** (quarantine on any error) and **retain-by-default** (mail is never deleted). Async throughout: aioimaplib for IMAP fetching, aiosmtplib for LMTP delivery. Deploy with **Docker Compose** or **Kubernetes** (kustomize).

## License

MIT

---

*Built with Claude AI for intelligent email management.*

