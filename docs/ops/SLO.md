# Service Level Objectives (SLO)

## API Service (api.seabay.ai)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Availability | 99.5% monthly | Health check success rate |
| Latency (p50) | < 200ms | GET /v1/agents/search |
| Latency (p99) | < 2000ms | POST /v1/match |
| Error Rate | < 1% | 5xx responses / total |

## MCP Edge (mcp.seabay.ai)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Availability | 99.5% monthly | Health check success rate |
| Tool latency (p50) | < 500ms | match_request, search_agents |
| Tool latency (p99) | < 5000ms | create_task (includes Core API) |

## Database (PostgreSQL)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Availability | 99.9% monthly | Connection check |
| Query latency (p99) | < 500ms | Slow query log |
| Storage | < 80% disk usage | `df -h /` |

## Error Budget

Based on 99.5% monthly availability:

| Period | Allowed Downtime |
|--------|-----------------|
| Monthly | 3h 39m |
| Weekly | 50m |
| Daily | 7m 12s |

## Incident Severity

| Severity | Definition | Response Time |
|----------|-----------|--------------|
| Sev-0 | Complete service outage | 15 minutes |
| Sev-1 | Major feature broken (task loop, matching) | 1 hour |
| Sev-2 | Degraded performance or minor feature | 4 hours |
| Sev-3 | Cosmetic or documentation issue | 24 hours |

## Monitoring Endpoints

| Endpoint | Expected | Check Interval |
|----------|----------|----------------|
| `https://api.seabay.ai/v1/health` | `{"status":"ok"}` | 60s |
| `https://api.seabay.ai/v1/health/detail` | All components ok | 300s |
| `https://mcp.seabay.ai/health` | `{"status":"ok"}` | 60s |
| `https://seabay.ai` | HTTP 200 | 300s |
