#!/bin/bash
#############################################
# Postal Inspector Installation Script
# Sets up the mail system on the host
#############################################

set -e

INSTALL_DIR="/opt/postal-inspector"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Postal Inspector Installer ==="
echo "Source: $SCRIPT_DIR"
echo "Target: $INSTALL_DIR"
echo ""

# Check for required permissions
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Insufficient permissions"
    echo ""
    echo "This installer requires elevated privileges for:"
    echo "  - Creating system directories (/opt/postal-inspector)"
    echo "  - Creating system user (vmail, uid 5000)"
    echo "  - Installing systemd services"
    echo "  - Setting file ownership for mail storage"
    echo ""
    echo "Run with: sudo $0"
    echo ""
    echo "Alternatively, manually ensure your user has:"
    echo "  - Write access to $INSTALL_DIR"
    echo "  - Membership in docker group"
    echo "  - Ability to create users or existing vmail user (uid 5000)"
    exit 1
fi

# Check dependencies
echo "Checking dependencies..."
for cmd in docker docker-compose; do
    if ! command -v $cmd &> /dev/null; then
        echo "ERROR: $cmd is required but not installed"
        exit 1
    fi
done
echo "  Dependencies OK"

# Create vmail user/group if not exists (matches containers)
if ! id -u vmail > /dev/null 2>&1; then
    echo "Creating vmail user (uid 5000)..."
    groupadd -g 5000 vmail 2>/dev/null || true
    useradd -u 5000 -g vmail -d /var/mail -s /sbin/nologin vmail 2>/dev/null || true
fi

# Create installation directory
echo "Creating installation directory..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/data/maildir"
mkdir -p "$INSTALL_DIR/data/maildir/.staging"
mkdir -p "$INSTALL_DIR/data/claude-state/ai-scanner"
mkdir -p "$INSTALL_DIR/data/claude-state/daily-briefing"
mkdir -p "$INSTALL_DIR/logs/ai-scanner"
mkdir -p "$INSTALL_DIR/logs/daily-briefing"
mkdir -p "$INSTALL_DIR/certs"

# Set correct ownership for mail and log directories
echo "Setting vmail ownership..."
chown -R 5000:5000 "$INSTALL_DIR/data/maildir"
chown -R 5000:5000 "$INSTALL_DIR/data/claude-state"
chown -R 5000:5000 "$INSTALL_DIR/logs"

# Copy files (only if newer, preserving user modifications)
echo "Copying files..."

# Use cp -n (no-clobber) for first install, rsync -u (update) for upgrades
if command -v rsync &> /dev/null; then
    # rsync -u only copies if source is newer
    rsync -a --update "$SCRIPT_DIR/services/" "$INSTALL_DIR/services/"
    rsync -a --update "$SCRIPT_DIR/scripts/" "$INSTALL_DIR/scripts/"
    rsync -a --update "$SCRIPT_DIR/docker-compose.yml" "$INSTALL_DIR/docker-compose.yml"
    echo "  Files synced (preserved local modifications)"
else
    # Fallback: only copy if destination doesn't exist
    if [ ! -d "$INSTALL_DIR/services" ]; then
        cp -r "$SCRIPT_DIR/services" "$INSTALL_DIR/"
    fi
    if [ ! -d "$INSTALL_DIR/scripts" ]; then
        cp -r "$SCRIPT_DIR/scripts" "$INSTALL_DIR/"
    fi
    if [ ! -f "$INSTALL_DIR/docker-compose.yml" ]; then
        cp "$SCRIPT_DIR/docker-compose.yml" "$INSTALL_DIR/"
    fi
    echo "  Files copied (skipped existing)"
fi

# Copy .env.example as .env if .env doesn't exist
if [ ! -f "$INSTALL_DIR/.env" ]; then
    if [ -f "$SCRIPT_DIR/.env.example" ]; then
        cp "$SCRIPT_DIR/.env.example" "$INSTALL_DIR/.env"
        echo "  Created .env from .env.example - EDIT THIS FILE!"
    fi
fi

# Install systemd services
echo "Installing systemd services..."
cp "$SCRIPT_DIR/systemd/"*.service /etc/systemd/system/ 2>/dev/null || true
cp "$SCRIPT_DIR/systemd/"*.timer /etc/systemd/system/ 2>/dev/null || true
systemctl daemon-reload

# Enable services
echo "Enabling services..."
systemctl enable postal-inspector.service 2>/dev/null || true
systemctl enable mail-backup.timer 2>/dev/null || true

# Build containers
echo "Building containers..."
cd "$INSTALL_DIR"
docker-compose build --quiet

# Deploy containers (idempotent - recreates only if changed)
echo "Deploying containers..."
docker-compose up -d

# Wait for health checks
echo "Waiting for services to become healthy..."
sleep 5

# Show status
echo ""
echo "=== Container Status ==="
docker-compose ps

echo ""
echo "=== Installation Complete ==="
echo ""
echo "All services have been installed, built, and deployed."
echo ""
echo "If this is a first install, complete these steps:"
echo "  1. Edit configuration: sudo nano $INSTALL_DIR/.env"
echo "  2. Add SSL certs to: $INSTALL_DIR/certs/"
echo "  3. Restart after config changes: cd $INSTALL_DIR && docker-compose up -d"
echo ""
echo "Useful commands:"
echo "  View logs: cd $INSTALL_DIR && docker-compose logs -f"
echo "  Restart:   cd $INSTALL_DIR && docker-compose restart"
echo "  Status:    cd $INSTALL_DIR && docker-compose ps"
echo ""
