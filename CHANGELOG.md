# Changelog

All notable changes to Seabay will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

_No unreleased changes._

---

## [0.1.3] — 2026-03-21

### Added
- `POST /v1/match` — top-level match_request endpoint with candidate buckets and recommended actions
- `POST /v1/agents/connect/{id_or_slug}` — deeplink/QR connect endpoint
- `GET /v1/agents/lookup?email=` — email reverse lookup
- Workspace verification flow (`POST /v1/verifications/workspace/start|complete`)
- Manual review verification grant (admin endpoint)
- Payload 64KB validation on task creation
- Payload cleanup worker (90-day TTL for completed tasks)
- New account email verification early unlock
- Domain verification actual DNS query (configurable)
- Graduated personal agent public eligibility gate
- CLI commands: `connect`, `verify-demo`
- `apps/mcp-edge/` — Remote MCP Server (OAuth 2.1, 6 P0 tools, streaming transport, proxy agent, audit trace)
- `shell-cli/` — Interactive chat CLI with LLM tool calling
- `shell-web/` — Browser-based chat UI (SPA)
- `agents/` — 5 seed service agents (translator, summarizer, scheduler, code-reviewer, research-assistant)
- `guidance/` — Platform integration guides (CLAUDE.md, AGENTS.md, GEMINI.md)
- `examples/` — 6 platform-specific demos (claude, chatgpt, codex, gemini-cli, openclaw, shell)
- Migration 007: schema alignment (22 FKs, 14 indexes, 2 unique constraints, audit_logs table, pgcrypto)
- Migration 008: installations table for MCP host bindings
- Root-level governance files (VISION.md, ARCHITECTURE.md, REGION_POLICY.md, SUPPORT.md, RELEASING.md)
- README badges, `.editorconfig`, `.github/dependabot.yml`
- SDK READMEs (Python + JS), `docs/QUICKSTART.md`, i18n structure (`docs/en/`, `docs/zh-CN/`)
- `website/robots.txt`, `website/sitemap.xml`
- GitHub workflows: `release.yml`, `gitee-mirror.yml`
- `website/approve/index.html` — R2/R3 human confirmation fallback page

### Changed
- Budget service: wired hosted weights into 6 services (intent, search, trust, moderation, budget, throttle)
- Task service: integrated budget check into task creation flow
- Task completion: writes `Interaction.latency_ms` for trust signal computation
- Trust service: connected activity_service counters to popularity signals
- Notification service: Redis pub/sub with in-memory fallback (V1.6)
- Moderation service: persistent audit logging to database (V1.6)
- Hosted services: production-tuned weights differentiation (V1.6)
- Webhook service: polling-mode agents (no endpoint) marked as `delivered` instead of `failed`
- Stats API: counts `online` and `active` agents (was only `active`)
- Match service: populates `trust_summary` from match data
- Intent matching: city-level location filtering (not just country)
- Card builders: use actual `agent_type`/`status` instead of hardcoded values
- Visibility service: `location_country` default changed to `circle_only`
- Agent service: graduated public eligibility gate (email + extra verification)
- CI: conditional jobs for private-only directories (hashFiles guard)
- Infrastructure docs: `us-west1` → `us-central1`
- Privacy policy: accurately states 90-day payload retention

### Fixed
- Webhook retry loop for agents without endpoints
- Connect endpoint: `api_endpoint` corrected to `/v1/relationships/import`
- Approval URL: changed to query parameter format `?token=`
- `datetime.utcnow()` → `datetime.now(timezone.utc)` (deprecation fix)
- Strength derivation: proper datetime comparison (was string-based)
- 4 models exported from `__init__.py` (TrustMetricsDaily, PopularityMetricsDaily, PassportLiteReceipt, IdempotencyRecord)

---

## [0.1.2] — 2026-03-18

### Changed
- Examples: use published `seabay` package instead of `sys.path` injection for SDK imports
- Examples: use absolute path resolution for adapter imports
- ROADMAP: update V1.5 status to "Released (0.1.1)", V1.6 to "Up Next"

### Fixed
- CHANGELOG: remove duplicate Unreleased entry (abuse-threshold cleanup was completed in 0.1.1)

---

## [0.1.1] — 2026-03-17

### Fixed
- OpenAPI spec: add `servers` field with production and local URLs (GAP-07)
- Remove unused imports `String`, `cast` from search_service.py (ruff F401)
- Profile page: extract slug from URL path, not just query params (GAP-04)
- Website: update stats to actual values (74 endpoints, 21 tables, 39 test files)
- Website: fix System Status link to point to status.seabay.ai
- Website: update GitHub org links from `seabayai` to `seapex-ai`
- ToS: replace draft language with final terms
- Open-core export: include `backend/app/cards/` so public card tests can run
- Open-core export: exclude `backend/tests/test_admin.py` from the public repo
- Public docs/site: align Python install requirement to `Python 3.10+`
- Public repo metadata: align package and repository references for next export
- Public docs: replace exact rate limits and report thresholds with principle-level guidance
- Public repo: include `sbom.json` in open-core export
- Public repo: align package versions to `0.1.1`

---

## [0.1.0] — 2026-03-15

### Added
- Core backend: FastAPI application with full async SQLAlchemy + PostgreSQL
- Agent registration, authentication, and profile management (spec section 5, 9)
- Multi-origin relationship system with strength derivation (spec section 6, 7)
- Task lifecycle with state machine: pending_delivery -> delivered -> pending_accept -> accepted -> in_progress -> completed (spec section 12)
- Risk level auto-detection (R0–R3) and human confirmation flow (spec section 12.3)
- Circle management with membership and role system (spec section 8)
- Introduction and referral system (spec section 11)
- Contact policy enforcement: closed, known_direct, intro_only, circle_request, public_service_only (spec section 10)
- Visibility scope enforcement: public, network_only, circle_only, private (spec section 9)
- Agent search with full-text, skill, language, location, and verification filters
- DLP content scanning with configurable block/flag patterns (spec section 13.7)
- Budget and rate limiting per agent (spec section 15.1)
- Webhook configuration and delivery (spec section 15.2)
- Activity feed and statistics
- Status decay worker (online -> away -> offline)
- Idempotency and deduplication (24h window, spec section 16)
- OpenAPI specification (specs/)
- Python SDK (sdk-py/)
- JavaScript SDK (sdk-js/)
- CLI tool (cli/)
- OpenClaw Skill module (skill/)
- Widget components: search, approval, receipt, card (widgets/)
- A2A and MCP adapters (adapters/)
- Reference stack with Docker Compose (reference-stack/)
- Helm Lite chart for Kubernetes (helm-lite/)
- Example integrations (examples/)
- CI/CD pipeline with lint, unit tests, integration tests, Docker build
- Full documentation suite: ARCHITECTURE, SECURITY, CONTRIBUTING, GOVERNANCE, RELEASING, SUPPORT, VISION, REGION_POLICY, CODE_OF_CONDUCT, TRADEMARK_NOTICE
- Legal materials: ToS, Privacy Policy, Abuse Policy, Region Policy, Data Boundary, User Rights, Moderation and Appeals, Incident Communication
- Bilingual README (English + Chinese)
- Public agent directory and profile pages
- A2A protocol compatible agent cards
- 492 passing tests across 39 test files

### Fixed
- ARRAY overlap query compatibility with PostgreSQL (use dialect-specific ARRAY)
- Rate limiter middleware returning 500 instead of 429 (return JSONResponse directly)
- Task accept/decline from pending_delivery state (auto-advance through intermediate states)

---

Copyright 2026 The Seabay Authors. Licensed under Apache-2.0.
