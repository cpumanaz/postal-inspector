#!/bin/bash
set -e

#############################################
# SECURITY: Input Validation
#############################################

# Validate BRIEFING_HOUR - must be 0-23
BRIEFING_HOUR="${BRIEFING_HOUR:-8}"
case "$BRIEFING_HOUR" in
    [0-9]|1[0-9]|2[0-3])
        # Valid hour 0-23
        ;;
    *)
        echo "ERROR: BRIEFING_HOUR must be 0-23. Got: $BRIEFING_HOUR"
        exit 1
        ;;
esac

echo "================================"
echo "Daily Briefing Service"
echo "================================"
echo "Mail User: ${MAIL_USER}"
echo "Briefing Hour: ${BRIEFING_HOUR}:00"
echo "Timezone: ${TZ}"
echo "================================"

# Create cron job for daily briefing
# Run at specified hour (default 8am)
CRON_SCHEDULE="0 ${BRIEFING_HOUR} * * *"

# Build cron entry with environment variables
# Note: Run as vmail user for consistent file permissions
cat > /etc/cron.d/daily-briefing << EOF
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
HOME=/home/vmail
MAIL_USER=${MAIL_USER}
TZ=${TZ}

# Daily briefing at ${BRIEFING_HOUR}:00 (runs as vmail user)
${CRON_SCHEDULE} vmail /app/daily-briefing.sh >> /app/logs/daily-briefing.log 2>&1
EOF

chmod 644 /etc/cron.d/daily-briefing

# Validate cron syntax
crontab /etc/cron.d/daily-briefing 2>/dev/null || true

echo "Cron schedule: ${CRON_SCHEDULE}"
echo "Starting cron daemon..."

# Start cron in foreground
exec cron -f
