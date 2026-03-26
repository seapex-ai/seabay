# Rollback Procedures

## Application Rollback

### Quick Rollback (< 5 minutes)

```bash
# 1. Identify the previous working commit
ssh into server
cd /opt/seabay
git log --oneline -5

# 2. Reset to previous commit
git reset --hard <previous_commit>

# 3. Rebuild and restart
docker compose -f docker-compose.prod.yml up -d --build api mcp-edge

# 4. Verify
curl -s http://localhost:8000/v1/health
curl -s http://localhost:8100/health
```

### Docker Image Rollback

If a specific Docker image version is known:

```bash
# Edit docker-compose.prod.yml to pin image version
# Then:
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

## Database Rollback

### Alembic Migration Rollback

```bash
cd /opt/seabay/backend

# Check current migration
alembic current

# Rollback one step
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>
```

### Full Database Rollback (from backup)

See [BACKUP-RESTORE.md](BACKUP-RESTORE.md) for database restore procedures.

## Rollback Decision Matrix

| Scenario | Action | ETA |
|----------|--------|-----|
| Bad deploy, services healthy | Git reset + rebuild | 5 min |
| Bad deploy, services crashed | Git reset + rebuild + restart Docker | 10 min |
| Bad migration, data intact | Alembic downgrade | 5 min |
| Bad migration, data corrupted | DB restore from backup | 15 min |
| Full server failure | New instance + full restore | 30 min |

## Post-Rollback Checklist

- [ ] All 4 containers healthy (`docker ps`)
- [ ] API health check passes (`/v1/health`)
- [ ] MCP Edge health check passes (`/health`)
- [ ] Git status clean
- [ ] Notify team of rollback reason
