"""DLP (Data Loss Prevention) scanning service.

Detection patterns per Freeze Pack #3 §8:
- BLOCKED: api_key, secret → 400
- WARNING: email, phone, url, address → 409 + dlp_override_token
"""

from __future__ import annotations

import re
import secrets

DLP_PATTERNS = {
    # Blocked patterns (cannot proceed)
    "api_key": re.compile(r"(sk_live_|sk_test_|api[_-]?key\s*[:=]\s*\S{10,})", re.IGNORECASE),
    "secret": re.compile(
        r"(secret\s*[:=]\s*\S{10,}|password\s*[:=]\s*\S{6,}|private[_-]?key)", re.IGNORECASE
    ),
    # Warning patterns (can override)
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"\+?\d[\d\s\-()]{7,}\d"),
    "url": re.compile(r"https?://[^\s<>\"']{4,}", re.IGNORECASE),
    "address": re.compile(
        r"\d{1,5}\s+\w+\s+(street|st|avenue|ave|road|rd|blvd|drive|dr|lane|ln|way|court|ct)\b",
        re.IGNORECASE,
    ),
}

BLOCKED_PATTERNS = {"api_key", "secret"}
WARNING_PATTERNS = {"email", "phone", "url", "address"}


def scan_content(text: str) -> list[dict]:
    """Scan text for DLP patterns. Returns list of findings."""
    if not text:
        return []

    findings = []
    for pattern_name, pattern_re in DLP_PATTERNS.items():
        matches = pattern_re.findall(text)
        if matches:
            is_blocked = pattern_name in BLOCKED_PATTERNS
            findings.append({
                "pattern": pattern_name,
                "action": "blocked" if is_blocked else "warning",
                "match_count": len(matches),
                "override_token": None if is_blocked else secrets.token_urlsafe(24),
            })

    return findings


def has_blocked(findings: list[dict]) -> bool:
    return any(f["action"] == "blocked" for f in findings)


def has_warning(findings: list[dict]) -> bool:
    return any(f["action"] == "warning" for f in findings)
