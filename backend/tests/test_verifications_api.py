"""Tests for verification API routes — email, github, domain.

Covers spec §14 (verification system).
Uses the full ASGI client from conftest.py.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, slug: str, agent_type: str = "service") -> dict:
    resp = await client.post("/v1/agents/register", json={
        "slug": slug,
        "display_name": f"Test {slug}",
        "agent_type": agent_type,
    })
    return resp.json()


class TestStartEmailVerification:
    """Test POST /v1/verifications/email/start."""

    @pytest.mark.asyncio
    async def test_start_email_verification(self, client: AsyncClient):
        agent = await _register(client, "verify-email-1")
        resp = await client.post(
            "/v1/verifications/email/start",
            params={"email": "test@example.com"},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert data["status"] == "pending"
        assert "verification_id" in data
        # DEV: code is returned for testing
        assert "_dev_code" in data

    @pytest.mark.asyncio
    async def test_start_email_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/v1/verifications/email/start",
            params={"email": "test@example.com"},
        )
        assert resp.status_code == 422  # missing auth header


class TestCompleteEmailVerification:
    """Test POST /v1/verifications/email/complete."""

    @pytest.mark.asyncio
    async def test_complete_email_with_valid_code(self, client: AsyncClient):
        agent = await _register(client, "verify-email-complete-1")
        # Start
        start_resp = await client.post(
            "/v1/verifications/email/start",
            params={"email": "complete@example.com"},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        start_data = start_resp.json()
        verification_id = start_data["verification_id"]
        code = start_data["_dev_code"]

        # Complete
        resp = await client.post(
            "/v1/verifications/email/complete",
            params={"verification_id": verification_id, "code": code},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "verified"

    @pytest.mark.asyncio
    async def test_complete_email_wrong_code(self, client: AsyncClient):
        agent = await _register(client, "verify-email-wrongcode")
        start_resp = await client.post(
            "/v1/verifications/email/start",
            params={"email": "wrong@example.com"},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        verification_id = start_resp.json()["verification_id"]

        resp = await client.post(
            "/v1/verifications/email/complete",
            params={"verification_id": verification_id, "code": "WRONGCODE"},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 400


class TestStartGithubVerification:
    """Test POST /v1/verifications/github/start."""

    @pytest.mark.asyncio
    async def test_start_github_verification(self, client: AsyncClient):
        agent = await _register(client, "verify-github-1")
        resp = await client.post(
            "/v1/verifications/github/start",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert "verification_id" in data
        assert "_dev_state" in data


class TestStartDomainVerification:
    """Test POST /v1/verifications/domain/start."""

    @pytest.mark.asyncio
    async def test_start_domain_verification(self, client: AsyncClient):
        agent = await _register(client, "verify-domain-1")
        resp = await client.post(
            "/v1/verifications/domain/start",
            params={"domain": "example.com"},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["domain"] == "example.com"
        assert data["dns_record_type"] == "TXT"
        assert data["dns_record_name"] == "_seabay.example.com"
        assert data["status"] == "pending"
        assert "dns_record_value" in data
        assert data["dns_record_value"].startswith("seabay-verify=")


class TestListMyVerifications:
    """Test GET /v1/verifications/my."""

    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient):
        agent = await _register(client, "verify-list-empty")
        resp = await client.get(
            "/v1/verifications/my",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    @pytest.mark.asyncio
    async def test_list_after_starting_verification(self, client: AsyncClient):
        agent = await _register(client, "verify-list-started")
        # Start email verification
        await client.post(
            "/v1/verifications/email/start",
            params={"email": "list@example.com"},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )

        resp = await client.get(
            "/v1/verifications/my",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 1
        assert data[0]["method"] == "email"
        assert data[0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_filter_by_method(self, client: AsyncClient):
        agent = await _register(client, "verify-list-filter")
        # Start both email and github
        await client.post(
            "/v1/verifications/email/start",
            params={"email": "filter@example.com"},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        await client.post(
            "/v1/verifications/github/start",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )

        # Filter by email
        resp = await client.get(
            "/v1/verifications/my",
            params={"method": "email"},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert all(v["method"] == "email" for v in data)

    @pytest.mark.asyncio
    async def test_list_verified_after_completion(self, client: AsyncClient):
        agent = await _register(client, "verify-list-complete")
        start_resp = await client.post(
            "/v1/verifications/email/start",
            params={"email": "verified@example.com"},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        data = start_resp.json()
        # Complete
        await client.post(
            "/v1/verifications/email/complete",
            params={"verification_id": data["verification_id"], "code": data["_dev_code"]},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )

        resp = await client.get(
            "/v1/verifications/my",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 200
        verifications = resp.json()["data"]
        verified = [v for v in verifications if v["status"] == "verified"]
        assert len(verified) >= 1
