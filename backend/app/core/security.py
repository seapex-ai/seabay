"""API key generation, hashing, and verification."""

from __future__ import annotations

import secrets

import bcrypt

from app.config import settings


def generate_api_key() -> str:
    """Generate a new API key: sk_live_{40 chars}."""
    random_part = secrets.token_urlsafe(30)  # ~40 chars
    return f"{settings.API_KEY_PREFIX}{random_part}"


def extract_key_prefix(api_key: str) -> str:
    """Extract indexable prefix from API key for O(1) lookup.

    Uses the first 12 chars after 'sk_live_' as the prefix.
    """
    raw = api_key.removeprefix(settings.API_KEY_PREFIX)
    return raw[:12]


def hash_api_key(api_key: str) -> str:
    """Hash an API key with bcrypt."""
    return bcrypt.hashpw(api_key.encode(), bcrypt.gensalt(settings.BCRYPT_ROUNDS)).decode()


def verify_api_key(api_key: str, api_key_hash: str) -> bool:
    """Verify an API key against its bcrypt hash."""
    return bcrypt.checkpw(api_key.encode(), api_key_hash.encode())
