# Postal Inspector - Mail Processor Service
# Replaces: mail-fetch + ai-scanner (bash)

FROM python:3.12-slim AS base

# Install uv (fast Rust-based package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Create vmail user (uid 5000 for consistency with other services)
RUN groupadd -g 5000 vmail && \
    useradd -u 5000 -g vmail -d /home/vmail -m -s /bin/bash vmail

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock README.md ./

# Install dependencies only (without dev dependencies, without the project itself)
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY src/ ./src/

# Now install the project itself (fast since dependencies are already installed)
RUN uv sync --frozen --no-dev

# Set environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/vmail

# Create required directories
RUN mkdir -p /app/logs /var/mail && \
    chown -R vmail:vmail /app /var/mail

# Switch to non-root user
USER vmail

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD uv run python -m postal_inspector health || exit 1

# Entry point
ENTRYPOINT ["uv", "run", "python", "-m", "postal_inspector"]
CMD ["scanner"]
