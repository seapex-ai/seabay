# @seabay/widgets

Embeddable UI widget rendering engine for Seabay V1.5. Renders `CardEnvelope` JSON into HTML for embedding task approval and match result cards in host applications.

## Prerequisites

- Node.js 18+
- npm 9+

## Setup

```bash
npm install
```

## Build

```bash
npm run build
```

Output goes to `dist/`.

## Exports

- `renderCard(envelope, level)` — render a card envelope at the specified level (0 = text, 1 = markdown, 2 = structured HTML)
- `validateCard(envelope)` — validate a card envelope against the JSON schema
- `validateAction(action)` — validate an action block
- `isExpired(envelope)` — check if a card has expired

## Schemas

JSON schemas for card types are in `schemas/`:

- `task-approval.json` — task approval card
- `match-result.json` — intent match result card

## Tests

Card contract tests live in the backend:

```bash
cd ../backend && pytest tests/test_cards.py
```
