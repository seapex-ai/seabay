"""Tests for report API routes — report agent, duplicate handling.

Covers spec §15.2 (report reasons), §5.1 (report handling thresholds).
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


class TestReportAgent:
    """Test POST /v1/agents/{id}/report."""

    @pytest.mark.asyncio
    async def test_report_agent_valid(self, client: AsyncClient):
        reporter = await _register(client, "report-reporter-1")
        target = await _register(client, "report-target-1")

        resp = await client.post(
            f"/v1/agents/{target['id']}/report",
            params={
                "reason_code": "spam",
                "notes": "Sending unsolicited messages",
            },
            headers={"Authorization": f"Bearer {reporter['api_key']}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["target_agent_id"] == target["id"]
        assert data["reason_code"] == "spam"
        assert data["status"] == "pending"
        assert "report_id" in data

    @pytest.mark.asyncio
    async def test_report_self_rejected(self, client: AsyncClient):
        agent = await _register(client, "report-self")

        resp = await client.post(
            f"/v1/agents/{agent['id']}/report",
            params={"reason_code": "spam"},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_report_nonexistent_agent(self, client: AsyncClient):
        reporter = await _register(client, "report-noexist-reporter")

        resp = await client.post(
            "/v1/agents/nonexistent_agent_id/report",
            params={"reason_code": "spam"},
            headers={"Authorization": f"Bearer {reporter['api_key']}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_report_invalid_reason_code(self, client: AsyncClient):
        reporter = await _register(client, "report-badreason-reporter")
        target = await _register(client, "report-badreason-target")

        resp = await client.post(
            f"/v1/agents/{target['id']}/report",
            params={"reason_code": "invalid_reason_xyz"},
            headers={"Authorization": f"Bearer {reporter['api_key']}"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_report_all_valid_reason_codes(self, client: AsyncClient):
        """All spec-defined reason codes should be accepted."""
        reporter = await _register(client, "report-allcodes-reporter")
        valid_codes = ["spam", "impersonation", "unsafe_request", "policy_violation", "harassment", "other"]
        for code in valid_codes:
            target = await _register(client, f"report-allcodes-target-{code}")
            resp = await client.post(
                f"/v1/agents/{target['id']}/report",
                params={"reason_code": code},
                headers={"Authorization": f"Bearer {reporter['api_key']}"},
            )
            assert resp.status_code == 201, f"Expected 201 for reason_code={code}, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_report_with_task_id(self, client: AsyncClient):
        reporter = await _register(client, "report-taskid-reporter")
        target = await _register(client, "report-taskid-target")

        resp = await client.post(
            f"/v1/agents/{target['id']}/report",
            params={
                "reason_code": "unsafe_request",
                "task_id": "task_fake_123",
                "notes": "Suspicious task",
            },
            headers={"Authorization": f"Bearer {reporter['api_key']}"},
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_report_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/v1/agents/some_id/report",
            params={"reason_code": "spam"},
        )
        assert resp.status_code == 422  # missing auth header


class TestDuplicateReportHandling:
    """Test duplicate report prevention."""

    @pytest.mark.asyncio
    async def test_duplicate_pending_report_rejected(self, client: AsyncClient):
        reporter = await _register(client, "report-dup-reporter")
        target = await _register(client, "report-dup-target")

        # First report
        resp1 = await client.post(
            f"/v1/agents/{target['id']}/report",
            params={"reason_code": "spam"},
            headers={"Authorization": f"Bearer {reporter['api_key']}"},
        )
        assert resp1.status_code == 201

        # Second report (same reporter, same target, still pending)
        resp2 = await client.post(
            f"/v1/agents/{target['id']}/report",
            params={"reason_code": "harassment"},
            headers={"Authorization": f"Bearer {reporter['api_key']}"},
        )
        assert resp2.status_code == 400

    @pytest.mark.asyncio
    async def test_different_reporters_can_report_same_agent(self, client: AsyncClient):
        reporter1 = await _register(client, "report-multi-r1")
        reporter2 = await _register(client, "report-multi-r2")
        target = await _register(client, "report-multi-target")

        resp1 = await client.post(
            f"/v1/agents/{target['id']}/report",
            params={"reason_code": "spam"},
            headers={"Authorization": f"Bearer {reporter1['api_key']}"},
        )
        assert resp1.status_code == 201

        resp2 = await client.post(
            f"/v1/agents/{target['id']}/report",
            params={"reason_code": "spam"},
            headers={"Authorization": f"Bearer {reporter2['api_key']}"},
        )
        assert resp2.status_code == 201


class TestReportServiceThresholds:
    """Test report threshold rules from spec."""

    def test_soft_freeze_threshold(self):
        from app.config import settings
        assert settings.REPORT_SOFT_FREEZE_THRESHOLD == 3

    def test_suspend_threshold(self):
        from app.config import settings
        assert settings.REPORT_SUSPEND_THRESHOLD == 5

    def test_suspend_greater_than_soft_freeze(self):
        from app.config import settings
        assert settings.REPORT_SUSPEND_THRESHOLD > settings.REPORT_SOFT_FREEZE_THRESHOLD
