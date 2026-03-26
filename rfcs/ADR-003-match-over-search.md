# ADR-003: match_request as Primary Discovery Tool

**Status:** Accepted
**Date:** 2026-03-25
**Authors:** Seabay Core Team

## Context

The MCP Edge initially shipped with `search_agents` as the primary discovery
tool. The test baseline requires `match_request` as a P0 tool for the Hosted
Conversation Plane.

## Decision

`match_request` is the primary discovery tool. `search_agents` remains available
as a lightweight fallback for simple keyword/filter searches.

### Rationale

- **Richer results:** `match_request` returns candidate buckets with match
  reasons, recommended actions, and trace IDs.
- **Intent-driven:** Creates an intent record for tracking and replay.
- **Natural language:** Accepts free-text descriptions alongside structured hints.
- **Baseline compliance:** Test baseline §3.1 requires `match_request` in P0 tools.

### Tool Priority

| Priority | Tool            | Use Case                          |
|----------|-----------------|-----------------------------------|
| Primary  | match_request   | Natural language discovery flows  |
| Fallback | search_agents   | Simple keyword/filter lookups     |

## Consequences

- Shell guidance (CLAUDE.md, AGENTS.md, llm.js, llm.py) all prioritize match_request.
- MCP Edge registers match_request first in the tool list.
- search_agents description notes: "Use match_request instead for richer results."
