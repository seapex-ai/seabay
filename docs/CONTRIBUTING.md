# Contributing to Seabay

Thank you for your interest in contributing to Seabay! Seabay follows an
**Open Core** model: the core platform (specs, SDKs, CLI, adapters, reference
stack, and documentation) is open-source under Apache 2.0. Hosted intelligence
services (matching, trust scoring, anti-abuse) are provided as managed services
and are not part of the public repository. The production website source is
also private and is not part of the public repository.

We welcome contributions to the open-core components.

---

## Getting Started

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:

```bash
git clone https://github.com/YOUR-USERNAME/seabay.git
cd seabay
```

3. **Set up the development environment:**

```bash
# Start infrastructure
docker compose up -d

# Backend dependencies
cd backend
pip install -e ".[dev]"

# Optional: SDK and CLI
cd ../sdk-py && pip install -e .
cd ../cli && pip install -e .
```

## Making Changes

1. Create a branch from `main`:

```bash
git checkout -b feature/your-change
```

Recommended branch names: `feature/`, `fix/`, `docs/`, `refactor/`, `test/`

2. Make your changes and ensure tests pass:

```bash
cd backend
ruff check .
pytest
```

3. Add or update tests when changing:
   - API contracts
   - Business logic
   - Database schema or migrations
   - Visibility, auth, or risk rules

Integration changes should be tested against PostgreSQL, not a mocked database.

## Submitting a Pull Request

1. Push your branch to your fork.
2. Open a PR against `main` on the upstream repository.
3. PR descriptions should include:
   - Summary of the change
   - Related issue (if any)
   - Testing performed
   - Migration or rollout notes (if applicable)
4. Sign off your commits (DCO):

```bash
git commit -s -m "Your commit message"
```

## Review and Merge

Merge requirements:

1. CI is green.
2. At least one maintainer approves.
3. Schema changes include Alembic migration updates.
4. API and spec changes stay aligned.

## Code Style

- Python is linted and formatted with `ruff`.
- Line length: 120 characters.
- Use clear names and add tests for non-trivial behavior.

## Reporting Issues

- **Bugs**: Use the [bug report template](https://github.com/seapex-ai/seabay/issues/new?template=bug_report.md)
- **Features**: Use the [feature request template](https://github.com/seapex-ai/seabay/issues/new?template=feature_request.md)
- **Security**: Email security@seabay.ai (do not open a public issue)

## Questions

Open a [GitHub Discussion](https://github.com/seapex-ai/seabay/discussions) or
file an issue for clarification.

---

Copyright 2026 The Seabay Authors.
Licensed under Apache-2.0.
