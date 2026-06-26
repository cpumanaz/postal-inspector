#!/bin/bash
set -euo pipefail
#############################################
# Postal Inspector Backup Script
# Creates compressed backup of maildir
# Runs daily, keeps configurable retention
#############################################

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-3}"
DATE=$(date +%Y-%m-%d)

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

log "Starting mail backup..."

# Use docker-compose to get container name dynamically
cd "$PROJECT_DIR"
BACKUP_FILE="${BACKUP_DIR}/mail-backup-${DATE}.tar.gz"
docker-compose exec -T imap tar -czf - -C /var mail > "$BACKUP_FILE"

if [ $? -ne 0 ]; then
    log "ERROR: Backup command failed!"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Verify backup file exists and is not empty
if [ ! -f "$BACKUP_FILE" ]; then
    log "ERROR: Backup file was not created!"
    exit 1
fi

# Check minimum size (empty tar.gz is ~20 bytes, require at least 100 bytes)
BACKUP_SIZE=$(stat -c%s "$BACKUP_FILE" 2>/dev/null || stat -f%z "$BACKUP_FILE" 2>/dev/null)
if [ "$BACKUP_SIZE" -lt 100 ]; then
    log "ERROR: Backup file too small (${BACKUP_SIZE} bytes) - likely empty or corrupted"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Verify backup integrity - test that tar can read the archive
if ! tar -tzf "$BACKUP_FILE" > /dev/null 2>&1; then
    log "ERROR: Backup file is corrupted - tar integrity check failed"
    rm -f "$BACKUP_FILE"
    exit 1
fi

SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log "Backup created and verified: mail-backup-${DATE}.tar.gz (${SIZE})"

# Remove backups older than retention period
log "Cleaning backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "mail-backup-*.tar.gz" -mtime +${RETENTION_DAYS} -delete

# List current backups
log "Current backups:"
ls -lh "${BACKUP_DIR}"/mail-backup-*.tar.gz 2>/dev/null || echo "  (none)"

log "Backup complete."
