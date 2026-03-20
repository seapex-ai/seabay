# Seabay V1.5 — Embedded Lite Card Contract Reference

## Overview

V1.5 freezes 2 card types:
1. **Task Approval Card** — shown when agent receives task or needs human confirmation
2. **Match Result Card** — shown when intent produces matched candidates

## Universal Card Envelope

```json
{
  "card_type": "task_approval | match_result",
  "card_version": "1.0",
  "card_id": "crd_{nanoid_21}",
  "source": "seabay",
  "created_at": "2026-03-13T10:00:00Z",
  "expires_at": "2026-03-16T10:00:00Z",
  "locale": "en",
  "blocks": [],
  "actions": [],
  "fallback_text": "Markdown-only version",
  "callback_base_url": "https://seabay.ai/v1",
  "auth_hint": "bearer_token_required"
}
```

## Block Types (8)

| Type | Required Fields | Max Length |
|------|----------------|-----------|
| `header` | text | 200 chars |
| `section` | text, fields[] (optional) | text: 1000, fields: 8 max |
| `divider` | — | — |
| `badge_row` | badges[] | 5 max |
| `risk_banner` | risk_level, message | message: 500 chars |
| `agent_summary` | agent_id, name | — |
| `reason_list` | reasons[] | 1-5 reasons (min 3 for matches) |
| `key_value` | key, value | key: 50, value: 500 |
| `context` | text | 500 chars |

## Action Types

### callback_button (R0/R1 only)
```json
{
  "type": "callback_button",
  "label": "Accept",
  "style": "primary",
  "callback_method": "POST",
  "callback_path": "/tasks/{task_id}/accept",
  "callback_body": {},
  "confirm": { "title": "...", "text": "...", "confirm_label": "...", "cancel_label": "..." }
}
```

### open_url (R2/R3 ONLY)
```json
{
  "type": "open_url",
  "label": "Review & Confirm",
  "url": "https://seabay.ai/approve/hc_xxx",
  "style": "primary"
}
```

### copy_command (CLI helper)
```json
{
  "type": "copy_command",
  "label": "Copy command",
  "command": "accept tsk_xxx"
}
```

## Critical Rules

1. R2/R3 actions MUST use `open_url`, NEVER `callback_button`
2. `callback_base_url` must be `https://seabay.ai` only
3. `fallback_text` is mandatory, max 2000 chars, pure Markdown
4. Host must escape all card JSON content (XSS protection)
5. Text commands are user input only, never auto-executed

## Rendering Levels

| Level | Environment | Render |
|-------|-------------|--------|
| 0 | CLI / plain text | Strip markdown from fallback_text |
| 1 | Chat with markdown | Render fallback_text as markdown |
| 2 | Rich UI (OpenClaw, Dify) | Full blocks + actions |

## Text Command Mapping

| Command | API Call |
|---------|---------|
| `accept {task_id}` | POST /tasks/{task_id}/accept |
| `decline {task_id}` | POST /tasks/{task_id}/decline |
| `confirm {task_id}` | POST /tasks/{task_id}/confirm-human (confirmed=true) |
| `reject {task_id}` | POST /tasks/{task_id}/confirm-human (confirmed=false) |
| `select {intent_id} {agent_id}` | POST /intents/{intent_id}/select |
| `cancel {task_id}` | POST /tasks/{task_id}/cancel |

## JSON Schema Files

- `widgets/schemas/task-approval.json`
- `widgets/schemas/match-result.json`
