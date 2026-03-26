# Backup & Restore Procedures

## Automated Backups

A daily backup cron runs at 03:00 UTC on the production server:

```bash
# /opt/seabay/backup.sh (runs via crontab)
docker exec seabay-postgres-1 pg_dump -U seabay seabay | gzip > \
  /opt/seabay/backups/seabay_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Retention Policy

| Type | Retention | Location |
|------|-----------|----------|
| Daily database dump | 7 days | `/opt/seabay/backups/` |
| Docker images | 3 most recent tags | GHCR `ghcr.io/seapex-ai/seabay` |
| Git history | Permanent | GitHub (internal + public) |

### Backup Verification

```bash
# List backups
ls -lh /opt/seabay/backups/

# Verify a backup is valid
gunzip -t /opt/seabay/backups/seabay_YYYYMMDD_HHMMSS.sql.gz
```

## Restore Procedures

### Database Restore

```bash
# 1. Stop the API (keep postgres running)
docker compose -f docker-compose.prod.yml stop api mcp-edge

# 2. Drop and recreate the database
docker exec seabay-postgres-1 psql -U seabay -c "DROP DATABASE seabay;"
docker exec seabay-postgres-1 psql -U seabay -c "CREATE DATABASE seabay;"

# 3. Restore from backup
gunzip -c /opt/seabay/backups/seabay_YYYYMMDD_HHMMSS.sql.gz | \
  docker exec -i seabay-postgres-1 psql -U seabay seabay

# 4. Restart services
docker compose -f docker-compose.prod.yml up -d api mcp-edge
```

### Full Server Restore

```bash
# 1. Clone from GitHub
git clone https://github.com/seapex-ai/seabay-internal.git /opt/seabay
cd /opt/seabay

# 2. Restore .env
# (copy from secure storage or reconstruct from template)

# 3. Start all services
docker compose -f docker-compose.prod.yml up -d

# 4. Restore database from backup
gunzip -c /path/to/backup.sql.gz | \
  docker exec -i seabay-postgres-1 psql -U seabay seabay
```

## Redis

Redis is used for rate limiting and SSE notifications only. It is ephemeral
and does not require backup. After a restart, rate limit counters reset and
SSE connections are re-established by clients.
