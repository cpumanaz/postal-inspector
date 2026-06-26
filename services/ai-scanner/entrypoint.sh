#!/bin/bash
set -e

echo "=========================================="
echo "AI Mail Scanner (Event-Driven)"
echo "=========================================="
echo "Mail directory: /var/mail/${MAIL_USER}"
echo "Mode: Real-time (inotify)"

# Verify Claude CLI exists
if ! command -v claude > /dev/null 2>&1; then
    echo "ERROR: Claude CLI not found."
    exit 1
fi
echo "Claude CLI: installed ($(claude --version 2>/dev/null || echo 'unknown version'))"

# Verify credentials file exists
if [ ! -f "/home/vmail/.claude/.credentials.json" ]; then
    echo "ERROR: Credentials file not found at /home/vmail/.claude/.credentials.json"
    echo "       Mount your credentials: -v ./secrets/claude-credentials.json:/home/vmail/.claude/.credentials.json:ro"
    exit 1
fi
echo "Credentials file: present"

# Verify API access with a minimal test call
echo "Testing API access..."
test_response=$(echo "Reply with exactly: OK" | timeout 30 claude --print 2>&1) || true
if echo "$test_response" | grep -qi "unauthorized\|invalid.*key\|authentication\|forbidden\|error"; then
    echo "ERROR: Claude API authentication failed."
    echo "Response: $test_response"
    echo "Check that your credentials are valid and not expired."
    exit 1
fi
if [ -z "$test_response" ]; then
    echo "ERROR: Claude API returned empty response. Check credentials and network."
    exit 1
fi
echo "Claude API: authenticated and working"

# Create required folders
mkdir -p /var/mail/${MAIL_USER}/.Quarantine/{cur,new,tmp}
mkdir -p /app/logs

echo "Starting scanner..."
echo ""

# Run the event-driven scanner (blocks and watches for new mail)
exec /app/mail-scanner.sh
