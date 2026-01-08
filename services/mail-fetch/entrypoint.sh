#!/bin/sh
set -e

# Generate fetchmailrc from environment
FETCHMAILRC="/tmp/.fetchmailrc"
IDFILE="/var/mail/.fetchmail.uidl"

#############################################
# SECURITY: Input Validation
#############################################

# Validate required environment variables exist
if [ -z "$UPSTREAM_SERVER" ]; then
    echo "ERROR: UPSTREAM_SERVER environment variable is required"
    exit 1
fi
if [ -z "$UPSTREAM_USER" ]; then
    echo "ERROR: UPSTREAM_USER environment variable is required"
    exit 1
fi
if [ -z "$UPSTREAM_PASS" ]; then
    echo "ERROR: UPSTREAM_PASS environment variable is required"
    exit 1
fi
if [ -z "$LOCAL_USER" ]; then
    echo "ERROR: LOCAL_USER environment variable is required"
    exit 1
fi

# SECURITY: Validate LOCAL_USER - prevent path traversal
# Only allow alphanumeric, underscore, hyphen
case "$LOCAL_USER" in
    *[!a-zA-Z0-9_-]*|"")
        echo "ERROR: LOCAL_USER contains invalid characters. Only [a-zA-Z0-9_-] allowed."
        exit 1
        ;;
esac

# SECURITY: Validate UPSTREAM_SERVER - basic hostname validation
# Allow alphanumeric, dots, hyphens (standard hostname chars)
case "$UPSTREAM_SERVER" in
    *[!a-zA-Z0-9.-]*|"")
        echo "ERROR: UPSTREAM_SERVER contains invalid characters."
        exit 1
        ;;
esac

# SECURITY: Validate UPSTREAM_PORT - must be numeric
UPSTREAM_PORT="${UPSTREAM_PORT:-993}"
case "$UPSTREAM_PORT" in
    *[!0-9]*|"")
        echo "ERROR: UPSTREAM_PORT must be numeric."
        exit 1
        ;;
esac

# SECURITY: Validate FETCH_INTERVAL - must be numeric and reasonable (10-3600 seconds)
FETCH_INTERVAL="${FETCH_INTERVAL:-300}"
case "$FETCH_INTERVAL" in
    *[!0-9]*|"")
        echo "ERROR: FETCH_INTERVAL must be numeric."
        exit 1
        ;;
esac
if [ "$FETCH_INTERVAL" -lt 10 ] || [ "$FETCH_INTERVAL" -gt 3600 ]; then
    echo "ERROR: FETCH_INTERVAL must be between 10 and 3600 seconds."
    exit 1
fi

# Ensure maildir structure exists (running as vmail user 5000)
mkdir -p "/var/mail/${LOCAL_USER}/new" 2>/dev/null || true
mkdir -p "/var/mail/${LOCAL_USER}/cur" 2>/dev/null || true
mkdir -p "/var/mail/${LOCAL_USER}/tmp" 2>/dev/null || true
mkdir -p "/var/mail/${LOCAL_USER}/.Quarantine/new" 2>/dev/null || true
mkdir -p "/var/mail/${LOCAL_USER}/.Quarantine/cur" 2>/dev/null || true
mkdir -p "/var/mail/${LOCAL_USER}/.Quarantine/tmp" 2>/dev/null || true

cat > "$FETCHMAILRC" << EOF
# Fetchmail configuration - auto-generated
# SECURITY: All variables validated before use
set daemon ${FETCH_INTERVAL}
set no bouncemail
set idfile ${IDFILE}

poll ${UPSTREAM_SERVER}
    protocol IMAP
    port ${UPSTREAM_PORT}
    uidl
    user "${UPSTREAM_USER}"
    password "${UPSTREAM_PASS}"
    ssl
    sslcertck
    nokeep
    mda "/usr/local/bin/deliver.sh /var/mail/${LOCAL_USER}"
EOF

# SECURITY: Restrict fetchmailrc permissions (contains password)
chmod 600 "$FETCHMAILRC"

echo "Starting fetchmail daemon (interval: ${FETCH_INTERVAL}s)..."
echo "Fetching from: ${UPSTREAM_SERVER} as ${UPSTREAM_USER}"
echo "Delivering to: /var/mail/${LOCAL_USER}/"

exec fetchmail -f "$FETCHMAILRC" -v --nodetach
