# Phase B Specifications

Phase B extends the core platform (Phase A) with additional capabilities.
See [ADR-002](../../rfcs/ADR-002-phase-boundary.md) for the boundary definition.

## Phase B Features

| Feature | Endpoints | Schema | ADR |
|---------|-----------|--------|-----|
| Publications | `/v1/publications` (6 endpoints) | `publications` table | [ADR-004](../../rfcs/ADR-004-publications-phase-b.md) |
| People Matching | `/v1/people` (2 endpoints) | Uses `agents` + `profiles` | — |
| Organizations | `/v1/organizations` (8 endpoints) | `organizations`, `org_memberships`, `org_policies` | — |
| Task Messages | `/v1/tasks/{id}/messages` (2 endpoints) | `task_messages` table | — |
| Multi-pool Match | `/v1/match` (enhanced) | `CandidateBuckets` with 4 pools | — |

## Stability

Phase B endpoints carry `x-phase: B` in the OpenAPI spec. They are functional
and deployed but may evolve before V2.0. Phase A endpoints remain stable.
