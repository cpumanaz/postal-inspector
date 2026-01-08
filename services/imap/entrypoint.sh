#!/bin/sh
set -e

#############################################
# SECURITY: Input Validation
#############################################

# Validate MAIL_USER - prevent path traversal
# Only allow alphanumeric, underscore, hyphen
case "$MAIL_USER" in
    *[!a-zA-Z0-9_-]*|"")
        echo "ERROR: MAIL_USER contains invalid characters or is empty. Only [a-zA-Z0-9_-] allowed."
        exit 1
        ;;
esac

# Validate MAIL_PASS is set
if [ -z "$MAIL_PASS" ]; then
    echo "ERROR: MAIL_PASS not set. Configure MAIL_PASS in .env file."
    exit 1
fi

# Create vmail user if not exists
if ! id -u vmail > /dev/null 2>&1; then
    addgroup -g 5000 vmail
    adduser -D -u 5000 -G vmail -h /var/mail vmail
fi

# Create users file from secrets
# Format: user:{PLAIN}password:uid:gid::home::
if [ -n "$MAIL_USER" ] && [ -n "$MAIL_PASS" ]; then
    echo "${MAIL_USER}:{PLAIN}${MAIL_PASS}:5000:5000::/var/mail/${MAIL_USER}::" > /etc/dovecot/users
    # SECURITY: Restrict users file permissions
    chmod 600 /etc/dovecot/users

    MAILDIR="/var/mail/${MAIL_USER}"

    # Create standard Maildir structure
    mkdir -p "$MAILDIR/cur" "$MAILDIR/new" "$MAILDIR/tmp"

    # Create standard IMAP folders
    mkdir -p "$MAILDIR/.Drafts/"{cur,new,tmp}
    mkdir -p "$MAILDIR/.Sent/"{cur,new,tmp}
    mkdir -p "$MAILDIR/.Trash/"{cur,new,tmp}
    mkdir -p "$MAILDIR/.Junk/"{cur,new,tmp}

    # Create AI Scanner folder (Quarantine only)
    mkdir -p "$MAILDIR/.Quarantine/"{cur,new,tmp}

    # Create subscriptions file
    cat > "$MAILDIR/subscriptions" << 'EOF'
Drafts
Sent
Trash
Junk
Quarantine
EOF

    # Set ownership
    chown -R vmail:vmail "$MAILDIR"
    chmod -R g+s "$MAILDIR"
fi

# Set ownership of mail directory
chown -R vmail:vmail /var/mail

echo "Starting Dovecot..."
echo "Mail user: ${MAIL_USER}"
echo "Folders: Inbox, Drafts, Sent, Trash, Junk, Quarantine"
exec "$@"
