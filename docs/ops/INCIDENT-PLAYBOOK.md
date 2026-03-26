# Incident Response Playbook

## Severity Classification

| Severity | Definition | Response | Escalation |
|----------|-----------|----------|------------|
| Sev-0 | Complete service outage | 15 min | Immediate |
| Sev-1 | Major feature broken | 1 hour | Within 30 min |
| Sev-2 | Degraded performance | 4 hours | If not resolved in 2h |
| Sev-3 | Minor issue | 24 hours | None |

## Playbook: API Unresponsive (Sev-0)

### Symptoms
- `https://api.seabay.ai/v1/health` returns non-200 or times out
- MCP tools fail with connection errors

### Steps

1. **Verify scope**
   ```bash
   curl -s https://api.seabay.ai/v1/health
   curl -s https://mcp.seabay.ai/health
   ```

2. **Check containers**
   ```bash
   ssh into server
   docker ps --format 'table {{.Names}}\t{{.Status}}'
   ```

3. **If API container is down:**
   ```bash
   docker logs seabay-api-1 --tail 50
   docker compose -f docker-compose.prod.yml restart api
   ```

4. **If postgres is down:**
   ```bash
   docker logs seabay-postgres-1 --tail 50
   docker compose -f docker-compose.prod.yml restart postgres
   # Wait for healthy, then restart api
   docker compose -f docker-compose.prod.yml restart api
   ```

5. **If all containers are up but API is slow:**
   ```bash
   # Check resources
   free -h
   df -h /
   docker stats --no-stream
   # Check for stuck queries
   docker exec seabay-postgres-1 psql -U seabay -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"
   ```

6. **If nothing works — full restart:**
   ```bash
   docker compose -f docker-compose.prod.yml down
   docker compose -f docker-compose.prod.yml up -d
   ```

## Playbook: MCP Edge Unresponsive (Sev-1)

### Steps

1. Check MCP Edge container:
   ```bash
   docker logs seabay-mcp-edge-1 --tail 50
   ```

2. Restart MCP Edge (does not affect API):
   ```bash
   docker compose -f docker-compose.prod.yml restart mcp-edge
   ```

3. Verify MCP tools:
   ```bash
   curl -s http://localhost:8100/.well-known/mcp.json | python3 -m json.tool
   ```

## Playbook: Database Corruption (Sev-0)

### Steps

1. Stop API to prevent further damage:
   ```bash
   docker compose -f docker-compose.prod.yml stop api mcp-edge
   ```

2. Assess damage:
   ```bash
   docker exec seabay-postgres-1 psql -U seabay -c "SELECT count(*) FROM agents;"
   ```

3. Restore from backup (see [BACKUP-RESTORE.md](BACKUP-RESTORE.md)):
   ```bash
   # Find latest backup
   ls -lh /opt/seabay/backups/
   # Restore
   gunzip -c /opt/seabay/backups/seabay_LATEST.sql.gz | \
     docker exec -i seabay-postgres-1 psql -U seabay seabay
   ```

4. Restart services:
   ```bash
   docker compose -f docker-compose.prod.yml up -d api mcp-edge
   ```

## Playbook: Disk Full (Sev-1)

### Steps

1. Check usage:
   ```bash
   df -h /
   du -sh /opt/seabay/backups/* | sort -rh | head
   docker system df
   ```

2. Quick cleanup:
   ```bash
   # Docker build cache
   docker builder prune -f
   # Old backups (keep 3 days)
   find /opt/seabay/backups -name "*.sql.gz" -mtime +3 -delete
   # Docker logs
   docker compose -f docker-compose.prod.yml logs --tail 0
   truncate -s 0 /var/lib/docker/containers/*/*-json.log
   ```

3. Verify freed space:
   ```bash
   df -h /
   ```

## Post-Incident

After any Sev-0 or Sev-1:

- [ ] Document what happened, when, and duration
- [ ] Identify root cause
- [ ] File follow-up issue if systemic fix needed
- [ ] Update this playbook if new scenario
