# Release Process

## Versioning

Seabay follows [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.x → 2.0): Breaking API changes, schema migrations required
- **MINOR** (1.5 → 1.6): New features, backward-compatible
- **PATCH** (1.5.0 → 1.5.1): Bug fixes, no new features

## Current Version

- **V1.5** — Initial release, 8-week MVP
- **V1.6** — Planned: public personal directory, semantic search, stranger discovery

## Release Checklist

### Pre-Release

1. All tests pass (`pytest tests/ -v`)
2. Linting clean (`ruff check backend/`)
3. OpenAPI spec updated if endpoints changed
4. CHANGELOG.md updated with release notes
5. Version bumped in:
   - `backend/pyproject.toml`
   - `sdk-py/pyproject.toml`
   - `sdk-js/package.json`
   - `cli/pyproject.toml`
   - `helm-lite/Chart.yaml`

### Build

1. Docker image built and tagged in GitHub Container Registry (`ghcr.io/seapex-ai/seabay`)
2. Python SDK published to PyPI (`seabay`, `seabay-cli`)
3. JavaScript SDK published to npm (`@seabayai/sdk`)
4. Helm chart packaged

### Release

1. Create git tag: `v{version}`
2. Push tag to the GitHub repository
3. GitHub Release created with:
   - Release notes
   - SBOM (Software Bill of Materials)
   - Docker image digest
4. Gitee mirror auto-synced

### Post-Release

1. Verify Docker image pulls successfully
2. Verify SDK installs correctly
3. Run smoke tests against staging
4. Update documentation site if needed

## SBOM

Each release includes a Software Bill of Materials (SBOM) in CycloneDX format:

```bash
pip install cyclonedx-bom
cyclonedx-py requirements backend/requirements.txt -o sbom.json
```

## Hotfix Process

1. Create branch from release tag: `hotfix/v{version}`
2. Apply fix with tests
3. Bump patch version
4. Follow standard release checklist
5. Cherry-pick to `main` if applicable

---

Copyright 2026 The Seabay Authors. Licensed under Apache-2.0.

