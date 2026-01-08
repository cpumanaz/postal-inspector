# Daily Briefing Service
# Generates AI-powered email summaries at 8am

FROM node:20-slim AS base

# Install Claude CLI
RUN npm install -g @anthropic-ai/claude-code

# Install required packages
RUN apt-get update && apt-get install -y \
    bash \
    coreutils \
    cron \
    procps \
    && rm -rf /var/lib/apt/lists/*

#############################################
# User Setup - Run as vmail for consistency
#############################################

# Create vmail user/group matching other services
RUN groupadd -g 5000 vmail && \
    useradd -u 5000 -g vmail -d /home/vmail -m -s /bin/bash vmail

WORKDIR /app

# Create directories with correct ownership
RUN mkdir -p /var/mail /home/vmail/.claude /app/logs && \
    chown -R vmail:vmail /home/vmail /app /app/logs

# Copy scripts with correct ownership
COPY --chown=vmail:vmail daily-briefing.sh /app/daily-briefing.sh
COPY --chown=vmail:vmail entrypoint.sh /entrypoint.sh

RUN chmod +x /app/daily-briefing.sh /entrypoint.sh

# Environment
ENV MAIL_USER=user \
    BRIEFING_HOUR=8 \
    TZ=UTC

# Note: Container runs as root for cron daemon, but scripts run as vmail
ENTRYPOINT ["/entrypoint.sh"]
