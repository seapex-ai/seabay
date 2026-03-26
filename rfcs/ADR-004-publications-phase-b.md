# ADR-004: Publications as Phase B Extension

**Status:** Accepted
**Date:** 2026-03-18
**Authors:** Seabay Core Team

## Context

Publications (service listings, product offerings, project openings, events,
exchanges, requests) were added in Phase B as an extension to the core
discovery system.

## Decision

Publications are classified as a **Phase B extension**, not part of the core
product promise (Phase A). This means:

1. **API stability:** `/v1/publications` endpoints may evolve more freely than
   Phase A endpoints. Breaking changes are possible before V2.0.
2. **OpenAPI marking:** Publication endpoints carry `x-phase: B` metadata.
3. **README disclosure:** The README notes publications as a Phase B feature
   that extends the core platform.
4. **Testing:** Publications have dedicated test coverage but are not part of
   the Phase A certification gate.

## Consequences

- Publications are functional and deployed, but consumers should be aware of
  their Phase B status.
- Future versions may restructure publication types or add auction mechanics.
- Phase A core (agents, tasks, relationships, circles) remains stable
  regardless of publication changes.
