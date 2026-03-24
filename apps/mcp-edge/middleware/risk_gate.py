"""Risk assessment gate for MCP tool invocations.

Implements the V1.5 risk framework (R0-R3) for the MCP Edge layer.
R2/R3 actions require human confirmation before execution.

Risk levels:
- R0: Pure information / search / public data — auto-execute
- R1: Low-risk coordination — auto-execute (user preference may override)
- R2: Messaging humans / sharing contacts / confirming on behalf — MUST confirm
- R3: Payment / ordering / offline meet / private data — MUST strong-confirm
"""

from __future__ import annotations

import logging
import re

from fastapi import HTTPException, status

from config import settings

logger = logging.getLogger("mcp-edge.risk_gate")

# Keywords that trigger elevated risk levels (aligned with Core API enums.py)
_R3_KEYWORDS = frozenset({
    "payment", "pay", "purchase", "buy", "order", "place_order",
    "checkout", "transfer", "withdraw", "meet_offline", "in_person",
    "read_private", "connect_mcp", "grant_access", "access_private",
})

_R2_KEYWORDS = frozenset({
    "booking", "reservation", "appointment", "email_send", "send_email",
    "contact_person", "dm_send", "message_human", "share_contact",
    "share_info", "confirm_on_behalf", "sign", "agree", "delete",
    "cancel_subscription",
})

# Patterns for DLP minimum check
_DLP_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    "phone": re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"),
    "api_key": re.compile(r"(?:sk|pk|api|key|token|secret)[_-][a-zA-Z0-9]{16,}"),
    "url_with_auth": re.compile(r"https?://[^@\s]+:[^@\s]+@"),
}


def check_risk(risk_level: str, tool_name: str) -> None:
    """Check if a tool invocation is allowed at the given risk level.

    R0 and R1 pass through. R2/R3 raise an HTTPException indicating
    that human confirmation is required.

    Args:
        risk_level: The assessed risk level (R0, R1, R2, R3)
        tool_name: Name of the tool being invoked

    Raises:
        HTTPException (403): If the risk level requires human confirmation
    """
    if risk_level in settings.RISK_REQUIRE_CONFIRM:
        logger.warning(
            "Risk gate blocked tool=%s risk=%s — requires human confirm",
            tool_name, risk_level,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "human_confirm_required",
                "risk_level": risk_level,
                "message": (
                    f"This action (risk level {risk_level}) requires human confirmation. "
                    "Use the confirm_human tool to approve or reject."
                ),
            },
        )

    logger.debug("Risk gate passed: tool=%s risk=%s", tool_name, risk_level)


def assess_risk_level(text: str) -> str:
    """Assess risk level from text content (description, payload, etc.).

    Uses keyword matching aligned with the Core API HIGH_RISK_KEYWORDS.
    Also runs minimum DLP pattern checks.

    Args:
        text: The text to assess

    Returns:
        Risk level string: "R0", "R1", "R2", or "R3"
    """
    text_lower = text.lower()

    # Check for R3 keywords first (highest priority)
    for keyword in _R3_KEYWORDS:
        if keyword in text_lower:
            logger.info("Risk assessed as R3: keyword=%s", keyword)
            return "R3"

    # Check for R2 keywords
    for keyword in _R2_KEYWORDS:
        if keyword in text_lower:
            logger.info("Risk assessed as R2: keyword=%s", keyword)
            return "R2"

    # Check DLP patterns
    dlp_result = run_dlp_check(text)
    if dlp_result["has_secrets"]:
        logger.info("Risk elevated to R3: DLP detected secrets")
        return "R3"
    if dlp_result["has_pii"]:
        logger.info("Risk elevated to R2: DLP detected PII")
        return "R2"

    return "R0"


def run_dlp_check(text: str) -> dict:
    """Run minimum DLP pattern check on text.

    Checks for:
    - Email addresses
    - Phone numbers
    - API keys / tokens / secrets
    - URLs with embedded credentials

    Returns:
        dict with keys: has_pii, has_secrets, patterns_found
    """
    patterns_found = []

    for pattern_name, regex in _DLP_PATTERNS.items():
        if regex.search(text):
            patterns_found.append(pattern_name)

    has_pii = any(p in patterns_found for p in ("email", "phone"))
    has_secrets = any(p in patterns_found for p in ("api_key", "url_with_auth"))

    return {
        "has_pii": has_pii,
        "has_secrets": has_secrets,
        "patterns_found": patterns_found,
    }
