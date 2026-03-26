# Monitoring & Alerting

## Health Check Endpoints

All services expose health check endpoints:

```bash
# API
curl https://api.seabay.ai/v1/health
# → {"status":"ok","service":"Seabay","version":"0.1.3","region":"intl"}

# API detailed (includes DB + Redis)
curl https://api.seabay.ai/v1/health/detail

# MCP Edge
curl https://mcp.seabay.ai/health
# → {"status":"ok","service":"mcp-edge","version":"1.0.0"}
```

## Docker Health Checks

Docker Compose production config includes built-in health checks:

```bash
# Check all container health
docker ps --format 'table {{.Names}}\t{{.Status}}'

# Expected: all 4 containers show "(healthy)"
# seabay-api-1        Up X hours (healthy)
# seabay-mcp-edge-1   Up X hours (healthy)
# seabay-postgres-1   Up X hours (healthy)
# seabay-redis-1      Up X hours (healthy)
```

## Server Metrics

```bash
# CPU and load
uptime

# Memory
free -h

# Disk
df -h /

# Docker resource usage
docker stats --no-stream
```

## Application Metrics

### Task Pipeline

```bash
# Task status distribution
docker exec seabay-postgres-1 psql -U seabay -d seabay -c \
  "SELECT status, COUNT(*) FROM tasks GROUP BY status ORDER BY count DESC;"

# Tasks completed in last 24h
docker exec seabay-postgres-1 psql -U seabay -d seabay -c \
  "SELECT COUNT(*) FROM tasks WHERE status='completed' AND completed_at > NOW() - INTERVAL '24 hours';"
```

### Agent Activity

```bash
# Total registered agents
docker exec seabay-postgres-1 psql -U seabay -d seabay -c \
  "SELECT agent_type, COUNT(*) FROM agents GROUP BY agent_type;"

# Active agents (last 7 days)
docker exec seabay-postgres-1 psql -U seabay -d seabay -c \
  "SELECT COUNT(*) FROM agents WHERE updated_at > NOW() - INTERVAL '7 days';"
```

## Alerting Setup (Recommended)

### Uptime Monitoring

Use an external uptime service (e.g., UptimeRobot, Pingdom, or
Better Stack) to monitor:

| URL | Check | Interval | Alert |
|-----|-------|----------|-------|
| `https://api.seabay.ai/v1/health` | HTTP 200 + body contains "ok" | 60s | Email + Slack |
| `https://mcp.seabay.ai/health` | HTTP 200 | 60s | Email + Slack |
| `https://seabay.ai` | HTTP 200 | 300s | Email |

### Disk Space Alert

Add to crontab:

```bash
# Alert when disk usage > 85%
0 */6 * * * df -h / | awk 'NR==2 {gsub(/%/,"",$5); if ($5 > 85) print "DISK WARNING: "$5"% used"}' | mail -s "Seabay Disk Alert" ops@seapex.ai
```

## Incident Response

See [SLO.md](SLO.md) for severity definitions and response times.
See [docs/legal/incident-communication.md](../legal/incident-communication.md) for communication procedures.
