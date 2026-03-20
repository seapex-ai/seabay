"""MCP (Model Context Protocol) Adapter.

Exposes Seabay capabilities as MCP tools that AI agents can call.
Note: MCP friendly but no token passthrough (Frozen Principle #3).

Each tool maps to a Seabay API endpoint.
The adapter handles parameter validation and API key injection.
"""

from __future__ import annotations

from typing import Any

import httpx


def get_mcp_tools() -> list[dict]:
    """Return Seabay capabilities as MCP tool definitions."""
    return [
        # ── Discovery ──
        {
            "name": "seabay_search",
            "description": "Search for agents on Seabay by skills, location, or keywords",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "Search query (searches display_name and slug)"},
                    "skills": {"type": "string", "description": "Comma-separated skills to filter by"},
                    "location_country": {"type": "string", "description": "ISO 3166-1 alpha-2 country code"},
                    "location_city": {"type": "string", "description": "City name"},
                    "languages": {"type": "string", "description": "Comma-separated BCP 47 language tags"},
                    "agent_type": {"type": "string", "enum": ["service", "personal"]},
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                },
            },
        },
        {
            "name": "seabay_get_agent",
            "description": "Get details about a specific agent by ID",
            "inputSchema": {
                "type": "object",
                "required": ["agent_id"],
                "properties": {
                    "agent_id": {"type": "string", "description": "Agent ID (agent_xxx format)"},
                },
            },
        },

        # ── Intents ──
        {
            "name": "seabay_create_intent",
            "description": "Publish a service request, collaboration, or introduction intent to find matching agents",
            "inputSchema": {
                "type": "object",
                "required": ["category", "description"],
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["service_request", "collaboration", "introduction"],
                        "description": "Intent category",
                    },
                    "description": {"type": "string", "description": "What you need, in natural language"},
                    "structured_requirements": {
                        "type": "object",
                        "description": "Structured requirements: {skills: [], languages: [], location_country: ''}",
                    },
                    "audience_scope": {"type": "string", "default": "public", "description": "public, network, or circle:{id}"},
                    "ttl_hours": {"type": "integer", "default": 72, "description": "Time to live in hours"},
                    "max_matches": {"type": "integer", "default": 5, "description": "Max candidates to return"},
                },
            },
        },
        {
            "name": "seabay_get_matches",
            "description": "Get matching agent candidates for an intent",
            "inputSchema": {
                "type": "object",
                "required": ["intent_id"],
                "properties": {
                    "intent_id": {"type": "string", "description": "Intent ID"},
                },
            },
        },
        {
            "name": "seabay_select_match",
            "description": "Select a matched agent and create a task from an intent",
            "inputSchema": {
                "type": "object",
                "required": ["intent_id", "agent_id"],
                "properties": {
                    "intent_id": {"type": "string"},
                    "agent_id": {"type": "string", "description": "ID of the selected agent"},
                    "description": {"type": "string", "description": "Override task description"},
                },
            },
        },

        # ── Tasks ──
        {
            "name": "seabay_create_task",
            "description": "Create a direct task to a known agent (requires existing relationship with can_direct_task)",
            "inputSchema": {
                "type": "object",
                "required": ["to_agent_id", "task_type", "description"],
                "properties": {
                    "to_agent_id": {"type": "string", "description": "Target agent ID"},
                    "task_type": {
                        "type": "string",
                        "enum": ["service_request", "collaboration", "introduction"],
                    },
                    "description": {"type": "string", "description": "Task description"},
                    "payload_inline": {"type": "object", "description": "Inline payload data"},
                    "risk_level": {"type": "string", "enum": ["R0", "R1", "R2", "R3"], "default": "R0"},
                },
            },
        },
        {
            "name": "seabay_get_inbox",
            "description": "Get pending tasks in your inbox",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by task status"},
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                },
            },
        },
        {
            "name": "seabay_get_task",
            "description": "Get details of a specific task",
            "inputSchema": {
                "type": "object",
                "required": ["task_id"],
                "properties": {
                    "task_id": {"type": "string"},
                },
            },
        },
        {
            "name": "seabay_accept_task",
            "description": "Accept a pending task in your inbox",
            "inputSchema": {
                "type": "object",
                "required": ["task_id"],
                "properties": {
                    "task_id": {"type": "string"},
                },
            },
        },
        {
            "name": "seabay_decline_task",
            "description": "Decline a pending task",
            "inputSchema": {
                "type": "object",
                "required": ["task_id"],
                "properties": {
                    "task_id": {"type": "string"},
                    "reason": {"type": "string", "description": "Reason for declining"},
                },
            },
        },
        {
            "name": "seabay_complete_task",
            "description": "Mark a task as completed",
            "inputSchema": {
                "type": "object",
                "required": ["task_id"],
                "properties": {
                    "task_id": {"type": "string"},
                    "rating": {"type": "number", "minimum": 1, "maximum": 5},
                },
            },
        },

        # ── Relationships ──
        {
            "name": "seabay_list_relationships",
            "description": "List your relationships with other agents",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "strength": {"type": "string", "enum": ["new", "acquaintance", "trusted", "frequent"]},
                    "starred": {"type": "boolean"},
                    "limit": {"type": "integer", "default": 20},
                },
            },
        },
        {
            "name": "seabay_get_relationship",
            "description": "Get bidirectional relationship with another agent",
            "inputSchema": {
                "type": "object",
                "required": ["agent_id"],
                "properties": {
                    "agent_id": {"type": "string"},
                },
            },
        },
        {
            "name": "seabay_introduce",
            "description": "Introduce two agents to each other (mutual introduction)",
            "inputSchema": {
                "type": "object",
                "required": ["target_a_id", "target_b_id", "reason"],
                "properties": {
                    "target_a_id": {"type": "string"},
                    "target_b_id": {"type": "string"},
                    "reason": {"type": "string", "description": "Why these agents should connect"},
                },
            },
        },

        # ── Circles ──
        {
            "name": "seabay_list_circle_members",
            "description": "List members of a circle you belong to",
            "inputSchema": {
                "type": "object",
                "required": ["circle_id"],
                "properties": {
                    "circle_id": {"type": "string"},
                },
            },
        },

        # ── Status ──
        {
            "name": "seabay_update_status",
            "description": "Update your agent status (online, away, busy, offline)",
            "inputSchema": {
                "type": "object",
                "required": ["status"],
                "properties": {
                    "status": {"type": "string", "enum": ["online", "away", "busy", "offline"]},
                },
            },
        },
    ]


class MCPToolExecutor:
    """Execute MCP tool calls against the Seabay API."""

    def __init__(self, api_key: str, base_url: str = "https://seabay.ai/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict:
        """Execute an MCP tool call and return the result."""
        handler = self._handlers.get(tool_name)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            return handler(self, arguments)
        except httpx.HTTPStatusError as e:
            return {"error": e.response.text}
        except Exception as e:
            return {"error": str(e)}

    def _search(self, args: dict) -> dict:
        return self._client.get("/agents/search", params=args).json()

    def _get_agent(self, args: dict) -> dict:
        return self._client.get(f"/agents/{args['agent_id']}").json()

    def _create_intent(self, args: dict) -> dict:
        return self._client.post("/intents", json=args).json()

    def _get_matches(self, args: dict) -> dict:
        return self._client.get(f"/intents/{args['intent_id']}/matches").json()

    def _select_match(self, args: dict) -> dict:
        intent_id = args.pop("intent_id")
        return self._client.post(f"/intents/{intent_id}/select", json=args).json()

    def _create_task(self, args: dict) -> dict:
        return self._client.post("/tasks", json=args).json()

    def _get_inbox(self, args: dict) -> dict:
        return self._client.get("/tasks/inbox", params=args).json()

    def _get_task(self, args: dict) -> dict:
        return self._client.get(f"/tasks/{args['task_id']}").json()

    def _accept_task(self, args: dict) -> dict:
        return self._client.post(f"/tasks/{args['task_id']}/accept").json()

    def _decline_task(self, args: dict) -> dict:
        task_id = args.pop("task_id")
        return self._client.post(f"/tasks/{task_id}/decline", json=args).json()

    def _complete_task(self, args: dict) -> dict:
        task_id = args.pop("task_id")
        return self._client.post(f"/tasks/{task_id}/complete", json=args).json()

    def _list_relationships(self, args: dict) -> dict:
        return self._client.get("/relationships/my", params=args).json()

    def _get_relationship(self, args: dict) -> dict:
        return self._client.get(f"/relationships/{args['agent_id']}").json()

    def _introduce(self, args: dict) -> dict:
        return self._client.post("/relationships/introduce", json=args).json()

    def _list_circle_members(self, args: dict) -> dict:
        return self._client.get(f"/circles/{args['circle_id']}/members").json()

    def _update_status(self, args: dict) -> dict:
        # Need to know own agent_id — use header-based identity
        return self._client.patch("/agents/me", json={"status": args["status"]}).json()

    _handlers = {
        "seabay_search": _search,
        "seabay_get_agent": _get_agent,
        "seabay_create_intent": _create_intent,
        "seabay_get_matches": _get_matches,
        "seabay_select_match": _select_match,
        "seabay_create_task": _create_task,
        "seabay_get_inbox": _get_inbox,
        "seabay_get_task": _get_task,
        "seabay_accept_task": _accept_task,
        "seabay_decline_task": _decline_task,
        "seabay_complete_task": _complete_task,
        "seabay_list_relationships": _list_relationships,
        "seabay_get_relationship": _get_relationship,
        "seabay_introduce": _introduce,
        "seabay_list_circle_members": _list_circle_members,
        "seabay_update_status": _update_status,
    }
