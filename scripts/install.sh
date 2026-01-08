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

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo $0)"
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

# Copy files
echo "Copying files..."
cp -r "$SCRIPT_DIR/services" "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/scripts" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/docker-compose.yml" "$INSTALL_DIR/"

# Copy config template if .env doesn't exist
if [ ! -f "$INSTALL_DIR/.env" ]; then
    if [ -f "$SCRIPT_DIR/config/env.template" ]; then
        cp "$SCRIPT_DIR/config/env.template" "$INSTALL_DIR/.env"
        echo "  Created .env from template - EDIT THIS FILE!"
    elif [ -f "$SCRIPT_DIR/.env" ]; then
        cp "$SCRIPT_DIR/.env" "$INSTALL_DIR/.env"
        echo "  Copied existing .env"
    fi
fi

# Install systemd services
echo "Installing systemd services..."
cp "$SCRIPT_DIR/systemd/"*.service /etc/systemd/system/ 2>/dev/null || true
cp "$SCRIPT_DIR/systemd/"*.timer /etc/systemd/system/ 2>/dev/null || true
systemctl daemon-reload

# Enable services
echo "Enabling services..."
systemctl enable postal-inspector.service
systemctl enable mail-backup.timer

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit configuration: sudo nano $INSTALL_DIR/.env"
echo "  2. Add SSL certs to: $INSTALL_DIR/certs/"
echo "  3. Start the stack: sudo systemctl start postal-inspector"
echo "  4. Check status: sudo systemctl status postal-inspector"
echo "  5. View logs: docker-compose -f $INSTALL_DIR/docker-compose.yml logs -f"
echo ""
