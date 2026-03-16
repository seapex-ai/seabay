# Governance

## Project Structure

Seabay is maintained by Avan Mo and the Seabay community. The project copyright is held by Galaxy Vision (Hangzhou) Intelligent Technology Co., Ltd. (see [NOTICE](../NOTICE)). "The Seabay Authors" in project documentation refers to the copyright holder and all contributors.

### Roles

**BDFL (Benevolent Dictator For Life) — V1.x Phase**

- **Avan Mo** — Founder, core maintainer, final decision authority
- All architectural decisions, feature scope, and release timing are approved by the BDFL during V1.x

**Maintainers**

- Have write access to the main repository
- Review and merge pull requests
- Triage issues and manage releases
- Enforce release, security, and access controls

**Contributors**

- Community members and approved contributors
- Work through the fork-and-PR workflow described in [CONTRIBUTING.md](CONTRIBUTING.md)

### Decision Process

1. **Proposals** — Open an issue, PR draft, or design note
2. **Review** — Maintainers review within 5 business days
3. **Decision** — BDFL makes final call on architectural changes; maintainers decide on implementation details
4. **Execution** — Approved changes are implemented via standard PR process

### Frozen Specifications

The following specifications are frozen for V1.5 and cannot be changed without BDFL approval:

- SQL Schema (13 core tables)
- OpenAPI endpoint contracts (44 endpoints)
- Enumeration definitions (30 types)
- Card contracts (2 card types)
- 14 immutable design principles

### Transition Plan

Post V2.0, governance will transition to a maintainer committee model with documented voting procedures.

## Contact

- GitHub: https://github.com/seapex-ai/seabay
- Email: governance@seabay.ai

---

Copyright 2026 The Seabay Authors. Licensed under Apache-2.0.
