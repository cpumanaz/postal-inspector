# Postal Inspector

**AI-powered self-hosted email server with intelligent threat detection and daily briefings.**

Tired of phishing emails slipping through? Want an AI assistant that reads your inbox and tells you what matters? Postal Inspector pulls mail from your existing provider (Gmail, O365, Fastmail, etc.) into your own secure server, where Claude AI scans every message for threats and sends you a personalized daily summary.

## Why Postal Inspector?

### Smarter Threat Detection

Traditional spam filters use rules and blocklists. They catch obvious spam but miss sophisticated attacks. Claude AI actually *reads* your email and *reasons* about it:

- "This email claims to be from Microsoft but the domain is `micros0ft.com`"
- "The sender says they're your CEO, but they're asking for gift cards via a Gmail address"
- "This 'invoice' attachment has an unusual filename pattern common in malware"

**Rule-based filters see patterns. AI understands intent.**

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

Mail is scanned *before* it reaches your inbox, not after. If the AI is uncertain or something fails, the email goes to Quarantine - never delivered by default. Suspicious mail can't slip through due to errors.

## Features

| Feature | Description |
|---------|-------------|
| **AI Security Scanner** | Every email analyzed for threats in real-time |
| **Daily Briefings** | Morning summary of what needs your attention |
| **Virus Scanning** | Attachments checked before delivery |
| **Instant Processing** | New mail scanned immediately, not on a schedule |
| **Secure by Default** | When in doubt, quarantine - nothing slips through |

### What the Scanner Catches

- Fake domains (`micros0ft.com`, `amaz0n.com`)
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

- Linux server with Docker 20.10+ and Docker Compose 2.0+
- [Claude subscription](https://claude.ai) (Pro, Max, or Max 200)
- Domain name with DNS control
- TLS certificate for your mail domain
- 1GB+ RAM (ClamAV needs ~512MB)
- Upstream IMAP provider (Gmail, O365, Fastmail, etc.)

Your Claude subscription covers all AI scanning and briefings - no additional API costs.

## Get Started

**[Installation Guide →](docs/GETTING-STARTED.md)**

## Under the Hood

Built on proven open-source components: Dovecot (IMAP), Fetchmail, ClamAV, and Claude CLI - all orchestrated with Docker Compose.

## License

MIT

---

*Built with Claude AI for intelligent email management.*

