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
echo "Running as: $(whoami) ($(id -u):$(id -g))"
echo "================================"

# Create crontab file for supercronic
# Format: minute hour * * * command
CRONTAB_FILE="/app/crontab"
cat > "$CRONTAB_FILE" << EOF
# Daily briefing at ${BRIEFING_HOUR}:00
0 ${BRIEFING_HOUR} * * * /app/daily-briefing.sh >> /app/logs/daily-briefing.log 2>&1
EOF

echo "Cron schedule: 0 ${BRIEFING_HOUR} * * *"
echo "Starting supercronic (non-root cron)..."

# Run supercronic in foreground
exec supercronic "$CRONTAB_FILE"
