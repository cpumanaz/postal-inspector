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

    # Create LMTP aliases file for address-based folder routing
    # Maps all addresses at domain to the mailbox user
    if [ -n "$MAIL_DOMAIN" ]; then
        echo "@${MAIL_DOMAIN}: ${MAIL_USER}" > /etc/dovecot/aliases
        chmod 644 /etc/dovecot/aliases
    fi

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

#############################################
# Generate LMTP Recipient Mapping
#############################################
# Configure Dovecot to accept all addresses at domain for LMTP
# All recipients will be delivered to MAIL_USER mailbox
LMTP_CONF="/etc/dovecot/lmtp-recipients.conf"

if [ -n "$MAIL_USER" ] && [ -n "$MAIL_DOMAIN" ]; then
    echo "Configuring LMTP to accept all addresses at ${MAIL_DOMAIN} -> ${MAIL_USER}"
    cat > "$LMTP_CONF" << EOF
# LMTP catch-all recipient mapping using userdb prefetch
# This creates a combined passdb+userdb that accepts all recipients
# and delivers them to the main user's mailbox

# Passdb with userdb prefetch - catches all LMTP recipients
# Must come BEFORE the normal passdb to catch alias addresses first
passdb {
  driver = static
  args = user=${MAIL_USER} uid=vmail gid=vmail home=/var/mail/${MAIL_USER} userdb_uid=vmail userdb_gid=vmail userdb_home=/var/mail/${MAIL_USER}
}
EOF
    chmod 644 "$LMTP_CONF"
fi

#############################################
# Generate Sieve Filter
#############################################
SIEVE_OUTPUT="/etc/dovecot/sieve/default.sieve"

if [ -n "$ALIAS_PREFIX" ]; then
    echo "Alias-based folders enabled: ${ALIAS_PREFIX}folder@domain -> folder"
    cat > "$SIEVE_OUTPUT" << EOF
require ["fileinto", "mailbox", "envelope", "variables"];

# Sieve rules for mail sorting
# Prefix configured via ALIAS_PREFIX: ${ALIAS_PREFIX}

# Alias-based folder routing: ${ALIAS_PREFIX}folder@domain -> folder
# Uses envelope "to" which is the LMTP RCPT TO address

if envelope :matches "to" "${ALIAS_PREFIX}*@*" {
    set :lower "folder" "\${1}";
    fileinto :create "\${folder}";
    stop;
}

# Fallback - keep everything else in INBOX
keep;
EOF
else
    echo "Alias-based folders disabled (set ALIAS_PREFIX in .env to enable)"
    cat > "$SIEVE_OUTPUT" << 'EOF'
require ["fileinto", "mailbox", "variables"];

# Sieve rules for mail sorting
# Alias routing disabled (ALIAS_PREFIX not set)

# Fallback - keep everything in INBOX
keep;
EOF
fi

# Set permissions so vmail can read sieve script
chmod 644 "$SIEVE_OUTPUT"

# Compile sieve script
sievec "$SIEVE_OUTPUT" 2>/dev/null || echo "Warning: sieve compilation failed"

# Ensure compiled sieve is also readable
chmod 644 "${SIEVE_OUTPUT%.sieve}.svbin" 2>/dev/null || true

echo "Starting Dovecot..."
echo "Mail user: ${MAIL_USER}"
echo "Folders: Inbox, Drafts, Sent, Trash, Junk, Quarantine"
exec "$@"
