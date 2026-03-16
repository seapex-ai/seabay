# Seabay — Incident Communication

**Effective Date:** 2026-03-15 (Seed / Invite-Only)
**Operator:** Galaxy Vision (Hangzhou) Intelligent Technology Co., Ltd.

---

## 1. Scope

This document covers how Seabay communicates incidents to affected users, partners, and the public.

## 2. Incident Types

| Type | Example |
|---|---|
| Regional service outage | API unavailable in a region |
| Database recovery | Data restoration from backup |
| Security vulnerability | Disclosed vulnerability affecting the platform |
| Mass false enforcement | Incorrect bulk suspension or restriction |
| Verification chain failure | Identity verification service disruption |
| Release integrity issue | Compromised or corrupted published artifact |

## 3. Communication Channels

| Channel | Use Case |
|---|---|
| Status page (when available) | Real-time service status |
| Email to affected users | Targeted incident notifications |
| Repository docs/incidents/ | Post-incident reports |
| security@seabay.ai | Security-specific disclosures |

## 4. Incident Report Structure

Public incident reports should include:

1. **What happened** — Clear description of the incident
2. **What was affected** — Scope of impact (users, regions, services)
3. **When it was detected** — Timeline of discovery
4. **How it was handled** — Immediate response actions
5. **How we will prevent recurrence** — Root cause and remediation

## 5. Response Time Targets

| Severity | Initial Communication | Full Report |
|---|---|---|
| Critical (service down) | Within 1 hour | Within 48 hours |
| High (partial degradation) | Within 4 hours | Within 5 business days |
| Medium (limited impact) | Within 24 hours | Within 10 business days |
| Low (informational) | Best effort | As needed |

## 6. Security Incidents

Security incidents follow the disclosure process outlined in [SECURITY.md](../SECURITY.md):

- Do not disclose publicly until a fix is available
- Coordinate with affected parties
- Provide a timeline for public disclosure
- Credit reporters (with permission)

## 7. Contact

- Incident inquiries: support@seabay.ai
- Security incidents: security@seabay.ai

---

Copyright 2026 Galaxy Vision (Hangzhou) Intelligent Technology Co., Ltd. Licensed under Apache-2.0.

