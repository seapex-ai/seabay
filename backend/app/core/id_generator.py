"""ID generator using nanoid with type prefix.

Format: {type_prefix}_{nanoid_21}
Examples: agt_V1StGXR8_Z5jdHi6B, tsk_abc123xyz456...
"""

from __future__ import annotations

from nanoid import generate

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_"
ID_LENGTH = 21

# Type prefixes for each entity
PREFIXES = {
    "agent": "agt",
    "profile": "prf",
    "profile_field_visibility": "pfv",
    "relationship_edge": "rel",
    "relationship_origin": "ori",
    "circle": "cir",
    "circle_membership": "cmb",
    "introduction": "itr",
    "intent": "int",
    "task": "tsk",
    "interaction": "ixn",
    "verification": "vrf",
    "report": "rpt",
    "rate_limit_budget": "rlb",
    "human_confirm_session": "hc",
    "circle_join_request": "cjr",
    "dlp_scan": "dlp",
    "passport_lite_receipt": "rcpt",
    "trust_metric": "tmd",
    "popularity_metric": "pmd",
    "card": "crd",
    "idempotency": "idmp",
    "receipt": "rcpt",
    "relationship": "rel",
    "origin": "ori",
    "membership": "cmb",
    "join_request": "cjr",
    "trust_metrics": "tmd",
    "pop_metric": "pmd",
}


def generate_id(entity_type: str) -> str:
    prefix = PREFIXES.get(entity_type, entity_type[:3])
    return f"{prefix}_{generate(ALPHABET, ID_LENGTH)}"
