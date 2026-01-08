# Getting Started with Mail Stack

This guide walks you through setting up Mail Stack from scratch. By the end, you'll have an AI-powered email server that fetches mail from your existing provider, scans it for threats, and delivers daily intelligent summaries.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Install Claude CLI](#install-claude-cli)
3. [Get TLS Certificates](#get-tls-certificates)
4. [Configure Upstream Provider](#configure-upstream-provider)
5. [Install Mail Stack](#install-mail-stack)
6. [Configure Mail Client](#configure-mail-client)
7. [Testing](#testing)
8. [Customization](#customization)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Hardware Requirements

- **CPU**: Any modern CPU (ARM or x86_64)
- **RAM**: 1GB minimum (512MB for ClamAV alone)
- **Storage**: 1GB + your expected mailbox size
- **Network**: Static IP or dynamic DNS recommended

### Software Requirements

- Linux server (Ubuntu 22.04+, Debian 12+, or similar)
- Docker 20.10+ and Docker Compose 2.0+
- Domain name with DNS control

### Install Docker

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Log out and back in, then verify
docker --version
docker-compose --version
```

---

## Install Claude CLI

Mail Stack uses Claude CLI for AI-powered email analysis. You need to install and authenticate it on the host machine.

### Install Claude CLI

```bash
# Install globally via npm
npm install -g @anthropic-ai/claude-code

# Or if you don't have npm
curl -fsSL https://claude.ai/install.sh | sh
```

### Authenticate Claude CLI

```bash
# Run Claude CLI to authenticate
claude

# Follow the prompts to:
# 1. Open the authentication URL in your browser
# 2. Log in with your Anthropic account
# 3. Authorize the CLI
```

### Verify Authentication

```bash
# Check that credentials are stored
ls -la ~/.claude/

# Test that Claude CLI works
echo "Hello, can you respond?" | claude --print
```

### Fix Credentials Permissions

The containers run as the `vmail` user (UID 5000). The credentials file must be readable:

```bash
# Make credentials readable by container
chmod 644 ~/.claude/.credentials.json
```

The `~/.claude/.credentials.json` file will be mounted into the containers (read-only) to provide authentication.

---

## Get TLS Certificates

Your IMAP server needs TLS certificates. The easiest way is using Let's Encrypt with certbot.

### Option A: Certbot with DNS Challenge (Recommended)

This works even if port 80 isn't available on your server.

```bash
# Install certbot
sudo apt update
sudo apt install certbot

# Get certificate using DNS challenge
sudo certbot certonly --manual --preferred-challenges dns -d mail.yourdomain.com
```

When prompted, create a DNS TXT record:
1. Go to your DNS provider
2. Add a TXT record for `_acme-challenge.mail.yourdomain.com`
3. Set the value to the string certbot displays
4. Wait 1-2 minutes for DNS propagation
5. Press Enter to continue

Certificates will be saved to:
- `/etc/letsencrypt/live/mail.yourdomain.com/fullchain.pem`
- `/etc/letsencrypt/live/mail.yourdomain.com/privkey.pem`

### Option B: Certbot with HTTP Challenge

If port 80 is available:

```bash
# Stop any web server using port 80
sudo certbot certonly --standalone -d mail.yourdomain.com
```

### Option C: Existing Certificates

If you already have certificates (from another service, or purchased):

```bash
# Just ensure you have:
# - fullchain.pem (certificate + intermediate chain)
# - privkey.pem (private key)
```

### Copy Certificates to Mail Stack

```bash
cd /path/to/mail-stack
mkdir -p certs

# Copy from Let's Encrypt
sudo cp /etc/letsencrypt/live/mail.yourdomain.com/fullchain.pem certs/
sudo cp /etc/letsencrypt/live/mail.yourdomain.com/privkey.pem certs/

# Fix permissions
sudo chown $USER:$USER certs/*.pem
chmod 600 certs/privkey.pem
chmod 644 certs/fullchain.pem
```

### Auto-Renewal

Set up automatic certificate renewal:

```bash
# Test renewal
sudo certbot renew --dry-run

# Add post-renewal hook to copy certs and restart mail-stack
sudo tee /etc/letsencrypt/renewal-hooks/deploy/mail-stack.sh << 'EOF'
#!/bin/bash
cp /etc/letsencrypt/live/mail.yourdomain.com/fullchain.pem /path/to/mail-stack/certs/
cp /etc/letsencrypt/live/mail.yourdomain.com/privkey.pem /path/to/mail-stack/certs/
cd /path/to/mail-stack && docker-compose restart imap
EOF

sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/mail-stack.sh
```

---

## Configure Upstream Provider

Mail Stack fetches mail from an existing IMAP provider. Here's how to configure common providers:

### Gmail

1. Enable IMAP in Gmail settings
2. Create an App Password (required with 2FA):
   - Go to Google Account > Security > 2-Step Verification
   - Scroll to "App passwords"
   - Generate a new password for "Mail"
   - Use this as `UPSTREAM_PASS`

```env
UPSTREAM_SERVER=imap.gmail.com
UPSTREAM_PORT=993
UPSTREAM_USER=you@gmail.com
UPSTREAM_PASS=xxxx-xxxx-xxxx-xxxx  # App password, not your Google password
```

### Microsoft 365 / Outlook.com

1. Enable IMAP in Outlook settings
2. For personal accounts, use your regular password
3. For work/school accounts, you may need an app password

```env
UPSTREAM_SERVER=outlook.office365.com
UPSTREAM_PORT=993
UPSTREAM_USER=you@outlook.com
UPSTREAM_PASS=your-password
```

### Fastmail

```env
UPSTREAM_SERVER=imap.fastmail.com
UPSTREAM_PORT=993
UPSTREAM_USER=you@fastmail.com
UPSTREAM_PASS=your-password  # Or app password
```

### Generic IMAP Provider

```env
UPSTREAM_SERVER=imap.yourprovider.com
UPSTREAM_PORT=993
UPSTREAM_USER=your-username
UPSTREAM_PASS=your-password
```

---

## Install Mail Stack

### Clone the Repository

```bash
git clone https://github.com/yourusername/mail-stack.git
cd mail-stack
```

### Configure Environment

```bash
# Copy the example configuration
cp .env.example .env

# Edit with your settings
nano .env
```

Complete `.env` example:

```env
# Timezone
TZ=America/New_York

# Local mail server credentials (you choose these)
MAIL_USER=john
MAIL_PASS=your-secure-local-password
MAIL_DOMAIN=mail.yourdomain.com

# Port for IMAP (only TLS)
IMAPS_PORT=993

# Upstream provider (where to fetch mail from)
UPSTREAM_SERVER=imap.gmail.com
UPSTREAM_PORT=993
UPSTREAM_USER=john@gmail.com
UPSTREAM_PASS=xxxx-xxxx-xxxx-xxxx

# How often to check for new mail (seconds)
FETCH_INTERVAL=300

# Daily briefing hour (24h format)
BRIEFING_HOUR=8

# Backup settings
BACKUP_DIR=/backups
BACKUP_RETENTION_DAYS=7
```

### Verify Certificates

```bash
# Ensure certs exist
ls -la certs/
# Should show fullchain.pem and privkey.pem
```

### Start the Stack

```bash
# Build and start all services
make build
make up

# Watch the logs
make logs
```

### Verify Services

```bash
# Check service status
make status

# Expected output - all services should be "Up" or "healthy"
```

---

## Configure Mail Client

### Desktop Clients (Thunderbird, Apple Mail, etc.)

| Setting | Value |
|---------|-------|
| **Incoming Server** | |
| Protocol | IMAP |
| Server | mail.yourdomain.com (or your server IP) |
| Port | 993 |
| Security | SSL/TLS |
| Username | Your `MAIL_USER` from .env |
| Password | Your `MAIL_PASS` from .env |
| **Outgoing Server** | |
| Use your upstream provider's SMTP | (Gmail, O365, etc.) |

### Mobile Clients (iOS Mail, Android)

Same settings as desktop. For sending, use your upstream provider's SMTP settings.

### Why No SMTP?

Mail Stack is designed for **receiving** mail. For **sending**, continue using your upstream provider (Gmail, O365, etc.). This avoids deliverability issues and keeps the setup simple.

---

## Testing

### Test IMAP Connection

```bash
# Using openssl
openssl s_client -connect mail.yourdomain.com:993

# You should see certificate info and "OK" from Dovecot
```

### Test Mail Fetch

```bash
# Trigger immediate fetch
make fetch-now

# Check fetch logs
make logs-fetch
```

### Test AI Scanner

```bash
# Send yourself a test email (from another account)
# Watch the scanner logs
make logs-scanner

# You should see:
# [timestamp] NEW: Subject: Your test subject
# [timestamp]   -> SAFE | Normal correspondence
```

### Test Daily Briefing

```bash
# Generate a briefing now (don't wait until 8am)
make test-briefing

# Check your inbox for the briefing email
```

---

## Customization

### Change Briefing Time

Edit `.env`:
```env
BRIEFING_HOUR=7  # 7am instead of 8am
```

Then restart:
```bash
make restart
```

### Adjust Fetch Interval

Edit `.env`:
```env
FETCH_INTERVAL=60  # Check every minute instead of 5 minutes
```

### Custom Sieve Rules

Edit `services/imap/sieve/default.sieve` to add custom mail filtering rules.

Example - sort by service account:
```sieve
# Emails to svc-github@yourdomain.com go to github folder
if envelope :matches "to" "svc-*@*" {
    set :lower "folder" "${1}";
    fileinto :create "${folder}";
    stop;
}
```

After editing, rebuild the imap container:
```bash
docker-compose build imap
docker-compose up -d imap
```

---

## Troubleshooting

### "Connection refused" on port 993

1. Check if imap service is running: `make status`
2. Check firewall: `sudo ufw status` or `sudo iptables -L`
3. Verify port mapping in docker-compose.yml

### "Certificate error" in mail client

1. Ensure certificate matches your domain
2. Check certificate validity: `openssl s_client -connect mail.yourdomain.com:993`
3. Some clients need you to trust the certificate manually

### Mail not being fetched

1. Check fetchmail logs: `make logs-fetch`
2. Verify upstream credentials in `.env`
3. Test upstream connection manually:
   ```bash
   docker-compose exec mail-fetch fetchmail -v
   ```

### AI Scanner not classifying emails

1. Check Claude CLI authentication:
   ```bash
   docker-compose exec ai-scanner claude --version
   ```
2. Check scanner logs: `make logs-scanner`
3. Verify `~/.claude` directory exists on host

### Daily briefing not generating

1. Check briefing service logs: `make logs-briefing`
2. Verify cron is running: `docker-compose exec daily-briefing pgrep cron`
3. Test manually: `make test-briefing`

### Permission errors

Mail files must be owned by vmail (uid 5000):
```bash
sudo chown -R 5000:5000 data/maildir/
```

### High memory usage

ClamAV uses significant RAM. If you're memory-constrained:
1. Consider disabling antivirus (remove from docker-compose.yml)
2. Or increase server RAM to at least 1GB

---

## DNS Setup (Optional but Recommended)

If you want to access your mail server by hostname:

### A Record
```
mail.yourdomain.com -> your-server-ip
```

### Reverse DNS (PTR)
Contact your hosting provider to set up reverse DNS for better deliverability if you plan to send mail through this server in the future.

---

## Security Checklist

Before going live:

- [ ] Strong password for `MAIL_PASS` (16+ characters)
- [ ] TLS certificates installed and valid
- [ ] Firewall allows only port 993 for IMAP
- [ ] Claude CLI authenticated on host
- [ ] Upstream provider using app password (not main password)
- [ ] Regular backups configured

---

## Next Steps

1. **Monitor logs** for the first few days: `make logs`
2. **Check Quarantine folder** for any false positives
3. **Enjoy your daily briefings** at 8am (or your configured hour)
4. **Set up backups**: Add `scripts/backup.sh` to crontab

---

## Getting Help

- Check [README.md](README.md) for command reference
- Open an issue on GitHub for bugs
- Review logs with `make logs` for troubleshooting

---

*Happy emailing with AI-powered security!*
