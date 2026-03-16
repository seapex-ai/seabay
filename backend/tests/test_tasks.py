"""Test task lifecycle and state machine."""

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task


async def _register(client: AsyncClient, slug: str, agent_type: str = "service") -> dict:
    resp = await client.post("/v1/agents/register", json={
        "slug": slug,
        "display_name": f"Test {slug}",
        "agent_type": agent_type,
    })
    return resp.json()


async def _advance_to_pending_accept(db_session: AsyncSession, task_id: str):
    """Simulate delivery worker advancing task to pending_accept state."""
    await db_session.execute(
        update(Task).where(Task.id == task_id).values(status="pending_accept")
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_create_task(client: AsyncClient):
    svc = await _register(client, "task-svc-1")
    user = await _register(client, "task-user-1", "personal")

    response = await client.post(
        "/v1/tasks",
        json={
            "to_agent_id": svc["id"],
            "task_type": "service_request",
            "description": "Translate document",
        },
        headers={"Authorization": f"Bearer {user['api_key']}"},
    )
    assert response.status_code == 201
    task = response.json()
    assert task["status"] == "pending_delivery"
    assert task["risk_level"] == "R0"
    assert task["requires_human_confirm"] is False


@pytest.mark.asyncio
async def test_task_accept_and_complete(client: AsyncClient, db_session: AsyncSession):
    svc = await _register(client, "task-svc-2")
    user = await _register(client, "task-user-2", "personal")

    # Create task
    create_resp = await client.post(
        "/v1/tasks",
        json={
            "to_agent_id": svc["id"],
            "task_type": "service_request",
            "description": "Simple task",
        },
        headers={"Authorization": f"Bearer {user['api_key']}"},
    )
    task_id = create_resp.json()["id"]

    # Simulate delivery (worker would do this)
    await _advance_to_pending_accept(db_session, task_id)

    # Accept (as service agent)
    accept_resp = await client.post(
        f"/v1/tasks/{task_id}/accept",
        headers={"Authorization": f"Bearer {svc['api_key']}"},
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "in_progress"

    # Complete (as either agent)
    complete_resp = await client.post(
        f"/v1/tasks/{task_id}/complete",
        json={"rating": 5.0, "notes": "Great work"},
        headers={"Authorization": f"Bearer {svc['api_key']}"},
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_task_decline(client: AsyncClient, db_session: AsyncSession):
    svc = await _register(client, "task-svc-3")
    user = await _register(client, "task-user-3", "personal")

    create_resp = await client.post(
        "/v1/tasks",
        json={
            "to_agent_id": svc["id"],
            "task_type": "service_request",
            "description": "Will be declined",
        },
        headers={"Authorization": f"Bearer {user['api_key']}"},
    )
    task_id = create_resp.json()["id"]

    # Simulate delivery (worker would do this)
    await _advance_to_pending_accept(db_session, task_id)

    decline_resp = await client.post(
        f"/v1/tasks/{task_id}/decline",
        json={"reason": "Not available"},
        headers={"Authorization": f"Bearer {svc['api_key']}"},
    )
    assert decline_resp.status_code == 200
    assert decline_resp.json()["status"] == "declined"


@pytest.mark.asyncio
async def test_high_risk_auto_detection(client: AsyncClient):
    svc = await _register(client, "task-svc-4")
    user = await _register(client, "task-user-4", "personal")

    response = await client.post(
        "/v1/tasks",
        json={
            "to_agent_id": svc["id"],
            "task_type": "service_request",
            "description": "Please process this payment of $100",
        },
        headers={"Authorization": f"Bearer {user['api_key']}"},
    )
    assert response.status_code == 201
    task = response.json()
    assert task["risk_level"] == "R3"
    assert task["requires_human_confirm"] is True


@pytest.mark.asyncio
async def test_inbox(client: AsyncClient):
    svc = await _register(client, "task-svc-5")
    user = await _register(client, "task-user-5", "personal")

    # Create a task
    await client.post(
        "/v1/tasks",
        json={
            "to_agent_id": svc["id"],
            "task_type": "service_request",
            "description": "Inbox test",
        },
        headers={"Authorization": f"Bearer {user['api_key']}"},
    )

    # Check inbox
    response = await client.get(
        "/v1/tasks/inbox",
        headers={"Authorization": f"Bearer {svc['api_key']}"},
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) >= 1
