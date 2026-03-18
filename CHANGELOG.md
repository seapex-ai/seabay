# Changelog

All notable changes to Seabay will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

_No unreleased changes._

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
