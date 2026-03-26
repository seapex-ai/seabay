# ADR-001: Task Status Machine Naming Convention

**Status:** Accepted
**Date:** 2026-03-15
**Authors:** Seabay Core Team

## Context

The test baseline specifies `approval_required` and `running` as task statuses.
The implementation uses `waiting_human_confirm` and `in_progress` respectively.

## Decision

We adopt `waiting_human_confirm` and `in_progress` for the following reasons:

### `waiting_human_confirm` over `approval_required`

- **Specificity:** `approval_required` is ambiguous — it could mean peer approval,
  admin approval, or human confirmation. `waiting_human_confirm` explicitly
  indicates the R2/R3 human-in-the-loop confirmation gate.
- **State machine clarity:** The status directly maps to the
  `HumanConfirmSession` model and the `/confirm-human` endpoint.
- **Spec alignment:** The frozen risk spec §7.2 defines this gate as
  "human confirmation" not "approval".

### `in_progress` over `running`

- **Industry convention:** `in_progress` is the most widely used term in task
  management systems (JIRA, Linear, GitHub Projects).
- **Consistency with A2A:** Google's Agent-to-Agent protocol uses `working`
  for active state; `in_progress` is closer in semantics.
- **Non-ambiguity:** `running` could be confused with a process/container state.

## Mapping Table

| Baseline Term       | Implementation Term       | Reason            |
|---------------------|---------------------------|-------------------|
| `approval_required` | `waiting_human_confirm`   | Specificity       |
| `running`           | `in_progress`             | Industry standard |

## Consequences

- SDK documentation and guidance files use the implementation terms.
- OpenAPI spec uses implementation terms with baseline aliases noted.
- No breaking change needed — baseline terms were never shipped in any release.
