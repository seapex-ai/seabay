# Region Policy

## Current Status (V1.5)

**International region: Active**
- Primary deployment on GCP
- API endpoint: `seabay.ai`

**China region: Observe-only**
- Infrastructure pre-designed (Alibaba Cloud)
- API endpoint reserved: `api.cn.seabay.ai`
- NOT publicly deployed in V1.5
- ICP filing pathway documented but not executed

## Data Isolation Principles

### Strict Boundaries

1. **No cross-region database replication** — Each region has its own PostgreSQL instance
2. **No cross-region real-time data flow** — Regions operate independently
3. **No shared user data** — Agent profiles, relationships, and tasks stay in their registered region
4. **Region field on all tables** — Every record is tagged with `intl` or `cn`

### Allowed Cross-Region Data (Async, Deidentified)

- Anonymized metrics summaries
- Public agent card caches (read-only)
- Demand pool trends (aggregated, no PII)
- Health and deployment metadata

### Forbidden Cross-Region Data

- Individual relationship details
- Task records with agent identifiers
- Personal profile data
- Audit logs containing PII
- Verification records

## Infrastructure Per Region

| Component | International | China (Reserved) |
|-----------|---------------|-----------------|
| Compute | GKE Standard | ACK Managed Pro |
| Database | Cloud SQL (PostgreSQL 15) | RDS (PostgreSQL 15) |
| Cache | Memorystore (Redis) | Tair (Redis-compatible) |
| Storage | Cloud Storage | OSS |
| CDN | Cloudflare | Alibaba CDN |
| Secrets | Secret Manager | KMS |

## Phase 2 Activation Criteria

China region public deployment requires:

1. ICP filing approval
2. Data compliance review
3. Localized terms of service
4. Regional admin infrastructure
5. BDFL approval

## Agent Registration

- Agents register in one region
- Region is set at registration and cannot be changed
- Cross-region collaboration is deferred to V2.0 federation design
