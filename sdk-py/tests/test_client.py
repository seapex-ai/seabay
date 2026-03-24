"""Unit tests for Seabay Python SDK — no live API or network required.

Tests type models, payload builders, and method signatures.
"""

import json

import pytest

from seabay.types import Agent, Intent, PaginatedList, RegisterResult, Task


class TestTypeModels:
    """Test Pydantic-like data models parse correctly."""

    def test_agent_from_dict(self):
        data = {
            "id": "agt_123",
            "slug": "test",
            "display_name": "Test",
            "agent_type": "service",
            "status": "online",
            "verification_level": "email",
        }
        agent = Agent(**data)
        assert agent.id == "agt_123"
        assert agent.slug == "test"
        assert agent.status == "online"

    def test_agent_extra_fields(self):
        data = {
            "id": "agt_1",
            "slug": "x",
            "display_name": "X",
            "agent_type": "personal",
            "status": "offline",
            "verification_level": "none",
            "bio": "hello",
            "skills": ["python"],
        }
        agent = Agent(**data)
        assert agent.id == "agt_1"

    def test_task_from_dict(self):
        data = {
            "id": "tsk_456",
            "from_agent_id": "agt_a",
            "to_agent_id": "agt_b",
            "task_type": "service_request",
            "status": "pending_accept",
            "risk_level": "R0",
        }
        task = Task(**data)
        assert task.id == "tsk_456"
        assert task.status == "pending_accept"
        assert task.risk_level == "R0"

    def test_task_status_values(self):
        for status in ["pending_delivery", "delivered", "pending_accept", "accepted",
                        "in_progress", "completed", "declined", "expired", "cancelled"]:
            task = Task(id="t", from_agent_id="a", to_agent_id="b",
                        task_type="service_request", status=status, risk_level="R0")
            assert task.status == status

    def test_register_result(self):
        data = {"id": "agt_789", "api_key": "sk_live_xxx", "slug": "my-agent",
                "display_name": "Test", "agent_type": "service", "created_at": "2026-01-01T00:00:00Z"}
        result = RegisterResult(**data)
        assert result.id == "agt_789"
        assert result.api_key == "sk_live_xxx"

    def test_paginated_list(self):
        data = {"data": [{"id": "1"}, {"id": "2"}], "has_more": True, "next_cursor": "2"}
        pl = PaginatedList(**data)
        assert len(pl.data) == 2
        assert pl.has_more is True
        assert pl.next_cursor == "2"

    def test_paginated_list_empty(self):
        data = {"data": [], "has_more": False}
        pl = PaginatedList(**data)
        assert len(pl.data) == 0
        assert pl.has_more is False
        assert pl.next_cursor is None

    def test_intent_from_dict(self):
        data = {"id": "int_1", "category": "service_request", "description": "need help",
                "status": "active", "from_agent_id": "agt_1"}
        intent = Intent(**data)
        assert intent.id == "int_1"


class TestModuleImports:
    """Test that SDK modules import correctly."""

    def test_import_client_class(self):
        from seabay.client import SeabayClient
        assert SeabayClient is not None

    def test_import_types(self):
        from seabay.types import Agent, Task, Intent, Circle, Relationship
        assert all(c is not None for c in [Agent, Task, Intent, Circle, Relationship])

    def test_import_package(self):
        import seabay
        assert hasattr(seabay, "SeabayClient") or hasattr(seabay, "client")


class TestClientMethodSignatures:
    """Test that SeabayClient has all expected methods without instantiation."""

    def test_has_expected_methods(self):
        from seabay.client import SeabayClient
        expected = [
            "register", "get_agent", "update_agent", "search_agents",
            "create_task", "get_task", "get_inbox", "accept_task",
            "decline_task", "complete_task", "cancel_task",
            "create_intent", "get_intent", "get_matches", "select_match",
            "health", "get_my_passports", "verify_passport", "revoke_passport",
        ]
        for method in expected:
            assert hasattr(SeabayClient, method), f"Missing method: {method}"

    def test_has_register_method(self):
        from seabay.client import SeabayClient
        assert hasattr(SeabayClient, "register")
