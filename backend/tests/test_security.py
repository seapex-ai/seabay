"""Tests for security module — API key generation and verification."""

from __future__ import annotations

from app.core.security import generate_api_key, hash_api_key, verify_api_key


class TestAPIKeyGeneration:
    """Test API key generation."""

    def test_key_has_prefix(self):
        """Generated keys should start with sk_live_."""
        key = generate_api_key()
        assert key.startswith("sk_live_")

    def test_key_is_unique(self):
        """Each generated key should be unique."""
        keys = {generate_api_key() for _ in range(10)}
        assert len(keys) == 10

    def test_key_sufficient_length(self):
        """Key should be long enough for security (at least 30 chars)."""
        key = generate_api_key()
        assert len(key) >= 30


class TestAPIKeyHashing:
    """Test API key hashing."""

    def test_hash_is_different_from_key(self):
        """Hash should not equal the original key."""
        key = generate_api_key()
        hashed = hash_api_key(key)
        assert hashed != key

    def test_hash_is_consistent_length(self):
        """All hashes should have consistent length."""
        hashes = [hash_api_key(generate_api_key()) for _ in range(5)]
        # bcrypt hashes are always 60 chars
        for h in hashes:
            assert len(h) >= 50


class TestAPIKeyVerification:
    """Test API key verification."""

    def test_correct_key_verifies(self):
        """Correct key should verify against its hash."""
        key = generate_api_key()
        hashed = hash_api_key(key)
        assert verify_api_key(key, hashed)

    def test_wrong_key_fails(self):
        """Wrong key should not verify."""
        key1 = generate_api_key()
        key2 = generate_api_key()
        hashed = hash_api_key(key1)
        assert not verify_api_key(key2, hashed)

    def test_empty_key_fails(self):
        """Empty key should not verify."""
        key = generate_api_key()
        hashed = hash_api_key(key)
        assert not verify_api_key("", hashed)

    def test_partial_key_fails(self):
        """Partial key should not verify."""
        key = generate_api_key()
        hashed = hash_api_key(key)
        assert not verify_api_key(key[:10], hashed)
