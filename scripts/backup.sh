#!/usr/bin/env bash
# Seabay database backup script
# Usage: ./scripts/backup.sh
# Crontab: 0 3 * * * /opt/seabay/scripts/backup.sh

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/seabay/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/seabay_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup..."

# Dump database
docker exec seabay-postgres-1 pg_dump -U seabay seabay | gzip > "$BACKUP_FILE"

# Verify backup
if gunzip -t "$BACKUP_FILE" 2>/dev/null; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "[$(date)] Backup completed: $BACKUP_FILE ($SIZE)"
else
    echo "[$(date)] ERROR: Backup verification failed!" >&2
    exit 1
fi

# Rotate old backups
find "$BACKUP_DIR" -name "seabay_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete
REMAINING=$(ls "$BACKUP_DIR"/seabay_*.sql.gz 2>/dev/null | wc -l)
echo "[$(date)] Retention: keeping $REMAINING backups (max ${RETENTION_DAYS} days)"
