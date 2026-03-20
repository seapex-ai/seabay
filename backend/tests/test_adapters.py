"""Tests for A2A and MCP adapters."""

from __future__ import annotations

import os
import sys

# Add adapters to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "adapters"))

from a2a.adapter import (
    a2a_card_to_agent,
    a2a_state_to_internal,
    a2a_task_to_internal,
    agent_to_a2a_card,
    create_a2a_error,
    create_a2a_message,
    extract_text_from_message,
    internal_state_to_a2a,
    internal_task_to_a2a,
)
from mcp.adapter import get_mcp_tools

# ── A2A Adapter Tests ──

class TestA2AAgentCard:
    def test_basic_card_conversion(self):
        agent = {
            "id": "agent_abc123",
            "slug": "translator-bot",
            "display_name": "Translator Bot",
            "agent_type": "service",
            "verification_level": "github",
            "contact_policy": "public_service_only",
            "visibility_scope": "public",
            "status": "online",
            "region": "intl",
        }
        profile = {
            "bio": "I translate documents",
            "skills": ["translation", "writing"],
            "languages": ["en", "ja"],
            "can_offer": ["translation"],
        }

        card = agent_to_a2a_card(agent, profile)
        assert card["name"] == "Translator Bot"
        assert card["description"] == "I translate documents"
        assert len(card["skills"]) == 2
        assert card["skills"][0]["id"] == "translation"
        assert card["authentication"]["schemes"] == ["bearer"]
        assert card["x-seabay"]["agent_id"] == "agent_abc123"
        assert card["x-seabay"]["verification_level"] == "github"

    def test_card_without_profile(self):
        agent = {"display_name": "Test", "slug": "test"}
        card = agent_to_a2a_card(agent)
        assert card["name"] == "Test"
        assert card["description"] is None
        assert card["skills"] == []

    def test_card_to_agent_reverse(self):
        card = {
            "name": "Helper Bot",
            "description": "I help with things",
            "url": "https://example.com",
            "skills": [
                {"id": "coding", "name": "coding"},
                {"id": "review", "name": "review"},
            ],
            "x-seabay": {
                "agent_type": "service",
                "languages": ["en"],
            },
        }
        agent = a2a_card_to_agent(card)
        assert agent["display_name"] == "Helper Bot"
        assert agent["bio"] == "I help with things"
        assert agent["skills"] == ["coding", "review"]
        assert agent["agent_type"] == "service"


class TestA2ATaskConversion:
    def test_internal_to_a2a_basic(self):
        task = {
            "id": "task_xyz",
            "status": "in_progress",
            "description": "Translate document",
            "risk_level": "R0",
            "from_agent_id": "agent_a",
            "to_agent_id": "agent_b",
        }
        result = internal_task_to_a2a(task)
        assert result["id"] == "task_xyz"
        assert result["status"]["state"] == "working"
        assert result["status"]["message"]["parts"][0]["text"] == "Translate document"

    def test_internal_to_a2a_completed(self):
        task = {"id": "t1", "status": "completed", "description": "Done"}
        result = internal_task_to_a2a(task)
        assert result["status"]["state"] == "completed"

    def test_internal_to_a2a_human_confirm(self):
        task = {
            "id": "t2",
            "status": "waiting_human_confirm",
            "description": "Payment",
            "approval_url": "https://seabay.ai/approve/tok123",
            "requires_human_confirm": True,
        }
        result = internal_task_to_a2a(task)
        assert result["status"]["state"] == "input-required"
        texts = [p["text"] for p in result["status"]["message"]["parts"]]
        assert any("approve" in t for t in texts)

    def test_internal_to_a2a_with_payload(self):
        task = {
            "id": "t3",
            "status": "completed",
            "description": "Result",
            "payload_inline": {"translated": "hello"},
        }
        result = internal_task_to_a2a(task)
        assert "artifacts" in result
        assert result["artifacts"][0]["parts"][0]["data"]["translated"] == "hello"

    def test_a2a_to_internal_basic(self):
        a2a_task = {
            "id": "a2a_task_1",
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": "Please translate this"}],
            },
        }
        result = a2a_task_to_internal(a2a_task)
        assert result["description"] == "Please translate this"
        assert result["task_type"] == "service_request"
        assert result["metadata"]["a2a_task_id"] == "a2a_task_1"

    def test_a2a_to_internal_with_data(self):
        a2a_task = {
            "id": "a2a_2",
            "message": {
                "parts": [
                    {"type": "text", "text": "Process this"},
                    {"type": "data", "data": {"key": "value"}},
                ],
            },
        }
        result = a2a_task_to_internal(a2a_task)
        assert result["payload_inline"] == {"key": "value"}

    def test_a2a_to_internal_with_extension(self):
        a2a_task = {
            "id": "a2a_3",
            "message": {"parts": [{"type": "text", "text": "Pay"}]},
            "x-seabay": {"risk_level": "R3", "task_type": "collaboration"},
        }
        result = a2a_task_to_internal(a2a_task)
        assert result["risk_level"] == "R3"
        assert result["task_type"] == "collaboration"


class TestA2AStateMapping:
    def test_all_internal_states_mapped(self):
        internal_states = [
            "draft", "pending_delivery", "delivered", "pending_accept",
            "accepted", "in_progress", "waiting_human_confirm",
            "completed", "declined", "expired", "cancelled", "failed",
        ]
        for state in internal_states:
            a2a = internal_state_to_a2a(state)
            assert a2a != "unknown", f"State {state} not mapped"

    def test_all_a2a_states_mapped(self):
        a2a_states = ["submitted", "working", "input-required", "completed", "canceled", "failed"]
        for state in a2a_states:
            internal = a2a_state_to_internal(state)
            assert internal != "pending_delivery" or state == "submitted"

    def test_roundtrip_key_states(self):
        assert internal_state_to_a2a("completed") == "completed"
        assert internal_state_to_a2a("failed") == "failed"
        assert internal_state_to_a2a("in_progress") == "working"


class TestA2AHelpers:
    def test_create_message(self):
        msg = create_a2a_message("user", "Hello")
        assert msg["role"] == "user"
        assert msg["parts"][0]["type"] == "text"
        assert msg["parts"][0]["text"] == "Hello"

    def test_create_message_with_data(self):
        msg = create_a2a_message("agent", "Result", data={"key": 1})
        assert len(msg["parts"]) == 2
        assert msg["parts"][1]["type"] == "data"

    def test_extract_text(self):
        msg = {
            "parts": [
                {"type": "text", "text": "Hello"},
                {"type": "data", "data": {}},
                {"type": "text", "text": "World"},
            ]
        }
        assert extract_text_from_message(msg) == "Hello\nWorld"

    def test_create_error(self):
        err = create_a2a_error("not_found", "Task not found")
        assert err["error"]["code"] == "not_found"
        assert err["error"]["message"] == "Task not found"


# ── MCP Adapter Tests ──

class TestMCPTools:
    def test_tools_list_not_empty(self):
        tools = get_mcp_tools()
        assert len(tools) >= 10

    def test_all_tools_have_schema(self):
        for tool in get_mcp_tools():
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    def test_tool_names_prefixed(self):
        for tool in get_mcp_tools():
            assert tool["name"].startswith("seabay_")

    def test_required_tools_present(self):
        tool_names = {t["name"] for t in get_mcp_tools()}
        required = {
            "seabay_search",
            "seabay_create_intent",
            "seabay_create_task",
            "seabay_get_inbox",
            "seabay_accept_task",
            "seabay_get_matches",
            "seabay_complete_task",
            "seabay_list_relationships",
            "seabay_introduce",
        }
        assert required.issubset(tool_names)

    def test_search_tool_schema(self):
        tools = {t["name"]: t for t in get_mcp_tools()}
        search = tools["seabay_search"]
        props = search["inputSchema"]["properties"]
        assert "q" in props
        assert "skills" in props
        assert "languages" in props

    def test_create_task_required_fields(self):
        tools = {t["name"]: t for t in get_mcp_tools()}
        create = tools["seabay_create_task"]
        assert "to_agent_id" in create["inputSchema"]["required"]
        assert "task_type" in create["inputSchema"]["required"]
