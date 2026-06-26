#############################################
# Mail Agent - AI Email Security Scanner
# Built on Claude Code CLI
#############################################

FROM node:20-slim AS base

# Install Claude Code CLI (the AI engine)
RUN npm install -g @anthropic-ai/claude-code

# Install system dependencies
RUN apt-get update && apt-get install -y \
    bash \
    coreutils \
    procps \
    inotify-tools \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

#############################################
# User Setup - Run as vmail for consistency
#############################################

# Create vmail user/group matching other services
RUN groupadd -g 5000 vmail && \
    useradd -u 5000 -g vmail -d /home/vmail -m -s /bin/bash vmail

#############################################
# Application Layer - Mail Scanning Logic
#############################################

WORKDIR /app

# Create directory structure with correct ownership
RUN mkdir -p /var/mail /home/vmail/.claude /app/logs && \
    chown -R vmail:vmail /home/vmail /app /app/logs

# Copy our mail scanning logic
COPY --chown=vmail:vmail mail-scanner.sh /app/mail-scanner.sh
COPY --chown=vmail:vmail entrypoint.sh /entrypoint.sh
RUN chmod +x /app/mail-scanner.sh /entrypoint.sh

# Environment defaults
ENV MAIL_USER=user \
    SCAN_INTERVAL=60 \
    TZ=UTC \
    HOME=/home/vmail

# Switch to vmail user for runtime
USER vmail

# Health check - verify Claude CLI is responsive
HEALTHCHECK --interval=5m --timeout=30s --start-period=60s \
    CMD claude --version > /dev/null 2>&1 || exit 1

ENTRYPOINT ["/entrypoint.sh"]
