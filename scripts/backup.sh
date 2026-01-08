#!/bin/bash
set -euo pipefail
#############################################
# Mail Backup Script
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
docker-compose exec -T imap tar -czf - -C /var mail > "${BACKUP_DIR}/mail-backup-${DATE}.tar.gz"

if [ $? -eq 0 ]; then
    SIZE=$(du -h "${BACKUP_DIR}/mail-backup-${DATE}.tar.gz" | cut -f1)
    log "Backup created: mail-backup-${DATE}.tar.gz (${SIZE})"
else
    log "ERROR: Backup failed!"
    exit 1
fi

# Remove backups older than retention period
log "Cleaning backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "mail-backup-*.tar.gz" -mtime +${RETENTION_DAYS} -delete

# List current backups
log "Current backups:"
ls -lh "${BACKUP_DIR}"/mail-backup-*.tar.gz 2>/dev/null || echo "  (none)"

log "Backup complete."
