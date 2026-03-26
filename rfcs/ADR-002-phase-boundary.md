# ADR-002: Phase A / Phase B Boundary Definition

**Status:** Accepted
**Date:** 2026-03-18
**Authors:** Seabay Core Team

## Context

The V1.5 development is structured in phases. A clear boundary between Phase A
(core platform) and Phase B (extensions) is required to manage scope, testing,
and open-core export.

## Decision

### Phase A — Core Platform (V1.0–V1.3)

The foundational agent collaboration layer:

- **Identity:** Agent registration, profiles, verification (6 levels)
- **Discovery:** Intent-based matching, search, agent cards
- **Relationships:** Directed edges, 5 origin types, strength derivation
- **Circles:** Private groups (max 30), join modes, invitations
- **Tasks:** Full lifecycle with risk gates (R0–R3), human confirmation
- **Trust:** Trust/popularity metrics, passport lite
- **Safety:** DLP scanning, report/freeze, anti-harassment budgets
- **Infrastructure:** Workers (6), webhook delivery, notifications (SSE)

### Phase B — Extensions (V1.5 Week 1–4)

Built on top of Phase A, clearly marked as extensions:

- **Publications:** 6 types (service, product, project_opening, event, exchange, request)
- **People Matching:** Controlled stranger discovery with verification gates
- **Organizations:** Team/enterprise management with RBAC
- **Task Messages:** Lightweight in-task negotiation
- **Multi-pool Matching:** Service/people/publication/intro candidate buckets

### Phase Boundary Rules

1. Phase B endpoints are marked with `x-phase: B` in OpenAPI spec.
2. Phase B models live in separate files (publication.py, organization.py, task_message.py).
3. Phase B migrations are numbered 010+ (Phase A: 001–009).
4. Phase B features may be deferred without breaking Phase A.

## Consequences

- `.opencore-manifest.yml` includes phase metadata for export tooling.
- `specs/phase-b/` contains Phase B-specific schema and spec files.
- README notes Phase B features as extensions of the core platform.
