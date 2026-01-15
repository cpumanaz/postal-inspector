# Daily Briefing Service
# Generates AI-powered email summaries at configured hour
# SECURITY: Runs entirely as non-root using supercronic

FROM node:20-slim AS base

# Install Claude CLI
RUN npm install -g @anthropic-ai/claude-code

# Install required packages (no cron - using supercronic instead)
RUN apt-get update && apt-get install -y \
    bash \
    coreutils \
    procps \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Install supercronic (cron replacement that runs as non-root)
ARG SUPERCRONIC_URL=https://github.com/aptible/supercronic/releases/download/v0.2.29/supercronic-linux-amd64
ARG SUPERCRONIC_SHA1SUM=cd48d45c4b10f3f0bfdd3a57d054cd05ac96812b
RUN curl -fsSLO "$SUPERCRONIC_URL" \
    && echo "${SUPERCRONIC_SHA1SUM}  supercronic-linux-amd64" | sha1sum -c - \
    && chmod +x supercronic-linux-amd64 \
    && mv supercronic-linux-amd64 /usr/local/bin/supercronic

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
    TZ=UTC \
    HOME=/home/vmail

# SECURITY: Run as non-root user
USER vmail

ENTRYPOINT ["/entrypoint.sh"]
