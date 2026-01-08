#!/bin/sh
#############################################
# Deduplicated Mail Delivery Agent
# Prevents duplicates by checking Message-ID
# against existing mail files (no database)
#############################################

set -e

MAILDIR="$1"

# Read email from stdin into temp file
TMPFILE=$(mktemp)
cat > "$TMPFILE"

# Extract Message-ID header (case-insensitive)
MSG_ID=$(grep -i "^Message-ID:" "$TMPFILE" | head -1 | sed 's/^[Mm]essage-[Ii][Dd]:[[:space:]]*//' | tr -d '\r\n')

# If Message-ID exists, check for duplicates in existing mail
if [ -n "$MSG_ID" ]; then
    # Search existing mail for this Message-ID
    if grep -rqF "$MSG_ID" "${MAILDIR}/cur" "${MAILDIR}/new" 2>/dev/null; then
        echo "DUPLICATE: $MSG_ID (skipped)" >&2
        rm -f "$TMPFILE"
        exit 0
    fi
fi

# Generate unique filename for maildir
FILENAME="$(date +%s).$$.$RANDOM.$(hostname)"
DESTFILE="${MAILDIR}/new/${FILENAME}"

# Deliver the message
mv "$TMPFILE" "$DESTFILE"
chmod 660 "$DESTFILE"

echo "DELIVERED: ${MSG_ID:-no-message-id} -> $DESTFILE" >&2
exit 0
