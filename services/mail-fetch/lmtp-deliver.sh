#!/bin/sh
#############################################
# Mail Staging Delivery Agent
# Saves mail to staging folder for AI scanning
# AI scanner will deliver via LMTP after scan
#############################################

set -e

LOCAL_USER="${LOCAL_USER:-postmaster}"
STAGING_DIR="/var/mail/.staging"

# Ensure staging directory exists
mkdir -p "$STAGING_DIR"

# Read email from stdin into temp file
TMPFILE=$(mktemp)
cat > "$TMPFILE"

# Extract Message-ID for logging
MSG_ID=$(grep -i "^Message-ID:" "$TMPFILE" | head -1 | sed 's/^[Mm]essage-[Ii][Dd]:[[:space:]]*//' | tr -d '\r\n')

# Extract original recipient from headers (for sieve filtering later)
# Priority: X-Envelope-To (Migadu), then X-Original-To, then Delivered-To, then To
ORIG_RCPT=$(grep -i "^X-Envelope-To:" "$TMPFILE" | head -1 | sed 's/^[^:]*:[[:space:]]*//' | tr -d '\r\n<>' | sed 's/.*<\([^>]*\)>.*/\1/')
if [ -z "$ORIG_RCPT" ]; then
    ORIG_RCPT=$(grep -iE "^(X-Original-To|Delivered-To|To):" "$TMPFILE" | head -1 | sed 's/^[^:]*:[[:space:]]*//' | tr -d '\r\n<>' | sed 's/.*<\([^>]*\)>.*/\1/')
fi

# Add X-Original-To header if we found a recipient and it's not already there
if [ -n "$ORIG_RCPT" ] && ! grep -qi "^X-Original-To:" "$TMPFILE"; then
    TMPFILE2=$(mktemp)
    echo "X-Original-To: ${ORIG_RCPT}" > "$TMPFILE2"
    cat "$TMPFILE" >> "$TMPFILE2"
    mv "$TMPFILE2" "$TMPFILE"
fi

# Generate unique filename for staging
TIMESTAMP=$(date +%s)
RAND=$(head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n')
STAGING_FILE="${STAGING_DIR}/${TIMESTAMP}.${RAND}.mail"

# Move to staging folder
mv "$TMPFILE" "$STAGING_FILE"
chmod 660 "$STAGING_FILE"

echo "STAGED for AI scan: ${MSG_ID:-no-message-id} -> ${STAGING_FILE} (orig: ${ORIG_RCPT:-none})" >&2
exit 0
