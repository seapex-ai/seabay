# Seabay — Region Policy

**Effective Date:** March 17, 2026
**Last Updated:** March 17, 2026

---

## 1. Single Project, Dual-Region Distribution

Seabay is a **single project** with **dual-region distribution**. There is no "China version" or "international version" — there is one Seabay with two deployment regions.

- Same codebase
- Same version number
- Same package name
- Different runtime environments and data boundaries

## 2. Why Two Regions

Regulatory, latency, and data sovereignty requirements make it necessary to operate separate infrastructure stacks in different regions. This is an infrastructure choice, not a product fork.

## 3. Principles

- **Same code, same version, same truth** — All regions run the same tagged release.
- **Data boundary by default** — Payload data does not cross regions by default.
- **No double-truth** — Documentation, policies, and feature sets do not diverge between regions.
- **High-risk thresholds are consistent** — Human confirmation requirements are the same regardless of region.
- **Download entry points may differ** — But the artifact version and content are identical.

## 4. China Region Status

- The China region is currently in **observe-only** mode.
- It is **not** publicly deployed or operated as a public consumer service in mainland China.
- Infrastructure pre-designed (Alibaba Cloud) but NOT activated in V1.5.
- ICP filing pathway documented but not executed.
- No ICP filing or public mainland operation is claimed at this stage.

## 5. What Cannot Be Done Across Regions

By default:
- Task payload is not replicated across regions
- Agent profiles are region-local
- Real-time cross-region consistency is not guaranteed
- Regional infrastructure operates independently

## 6. Regional Differences (Overlay, Not Fork)

Any region-specific behavior is implemented as an **overlay** on the shared codebase, not as a fork. Examples include:
- CDN and download mirror endpoints
- Container registry mirrors
- Region-specific compliance checks

These overlays never change the core logic, API behavior, or version truth.

## 7. Contact

- Regional inquiries: support@seabay.ai
- Legal inquiries: avan@seapex.ai

---

Copyright 2026 The Seabay Authors. Licensed under Apache-2.0.

