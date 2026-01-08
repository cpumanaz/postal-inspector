#!/bin/bash
set -e

echo "=========================================="
echo "AI Mail Scanner (Event-Driven)"
echo "=========================================="
echo "Mail directory: /var/mail/${MAIL_USER}"
echo "Mode: Real-time (inotify)"

# Verify Claude CLI is working
if ! claude --version > /dev/null 2>&1; then
    echo "ERROR: Claude CLI not working. Check credentials mount."
    exit 1
fi

echo "Claude CLI: authenticated"

# Create required folders
mkdir -p /var/mail/${MAIL_USER}/.Quarantine/{cur,new,tmp}
mkdir -p /app/logs

echo "Starting scanner..."
echo ""

# Run the event-driven scanner (blocks and watches for new mail)
exec /app/mail-scanner.sh
