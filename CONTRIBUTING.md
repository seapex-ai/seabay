# Contributing to Seabay

Thank you for your interest in contributing to Seabay.

## How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Ensure tests pass
5. Submit a pull request

## Developer Certificate of Origin (DCO)

All contributions must be signed off under the [Developer Certificate of Origin](https://developercertificate.org/). By adding a `Signed-off-by` line to your commit messages, you certify that you have the right to submit the contribution under the project's license.

```
git commit -s -m "Your commit message"
```

This adds a line like: `Signed-off-by: Your Name <your@email.com>`

## Code Style

- Python: Follow PEP 8. Use `ruff` for linting.
- TypeScript/JavaScript: Use Prettier defaults.
- Commit messages: Use conventional commits (`feat:`, `fix:`, `docs:`, `chore:`).

## Issues and Discussions

- Use GitHub Issues for bug reports and feature requests.
- Be specific: include steps to reproduce, expected behavior, and actual behavior.

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.

## Questions

For questions about contributing, email avan@seapex.ai.

## Development Setup

### Prerequisites
- Python 3.10+
- Docker and Docker Compose
- Node.js 18+ (for JS SDK)

### Local Development
```bash
# Clone and enter the repo
git clone https://github.com/seapex-ai/seabay.git
cd seabay

# Start PostgreSQL and Redis
docker compose up -d postgres redis

# Install backend dependencies
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload --port 8000

# Run tests
pytest
pytest -m integration  # requires running PostgreSQL
```

### SDK Development
```bash
# Python SDK
cd sdk-py && pip install -e .

# JavaScript SDK
cd sdk-js && npm install && npm run build
```
