"""LLM integration for Seabay Shell — connects to any OpenAI-compatible endpoint."""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx

from seabay_shell.config import ShellConfig

# System prompt that teaches the LLM about Seabay capabilities
SYSTEM_PROMPT = """\
You are Seabay Shell, a natural language interface for the Seabay Agent platform.
Seabay is a cross-platform agent connection and collaboration control layer.

You help users:
- Find and discover agents (translation, summarization, scheduling, code review, research, etc.)
- Create tasks and send them to agents
- Check their inbox for incoming tasks
- Accept or decline tasks
- Monitor task status and get results

IMPORTANT RULES:
1. When the user wants to find an agent, use the search_agents tool first.
2. When the user wants to send work to an agent, use create_task.
3. When the user asks about their tasks, use check_inbox or get_task.
4. For high-risk operations (R2/R3), always ask for user confirmation.
5. Be conversational and helpful — translate natural language into the right tool calls.
6. When showing results, be concise but include key details (name, skills, status).
7. If no agents match, suggest broadening the search or trying different terms.
8. Always respond in the same language the user is using.

Available agent types on the platform:
- Service agents: automated agents that perform specific tasks (translation, summarization, etc.)
- Personal agents: represent individual users

Task statuses: pending_delivery, delivered, pending_accept, accepted, in_progress, waiting_human_confirm, completed, failed, declined, cancelled, expired
Risk levels: R0 (public search), R1 (low-risk coordination), R2 (contact real people), R3 (payments/irreversible)
"""

# Tool definitions for the LLM
SEABAY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_agents",
            "description": "Search for agents on the Seabay platform by skills, location, language, or keywords.",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {
                        "type": "string",
                        "description": "Free-text search query",
                    },
                    "skills": {
                        "type": "string",
                        "description": "Comma-separated skills to filter by (e.g. 'translation,localization')",
                    },
                    "location": {
                        "type": "string",
                        "description": "Location filter (city or country)",
                    },
                    "language": {
                        "type": "string",
                        "description": "Language code filter (e.g. 'en', 'zh', 'ja')",
                    },
                    "agent_type": {
                        "type": "string",
                        "enum": ["service", "personal"],
                        "description": "Type of agent to search for",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a new task and send it to a specific agent. Use this when the user wants to delegate work.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to_agent_id": {
                        "type": "string",
                        "description": "ID of the agent to send the task to",
                    },
                    "task_type": {
                        "type": "string",
                        "description": "Type of task (e.g. 'service_request', 'collaboration')",
                        "default": "service_request",
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description of what the user wants done",
                    },
                },
                "required": ["to_agent_id", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_inbox",
            "description": "Check the user's task inbox for incoming and active tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by task status",
                        "enum": [
                            "pending_accept",
                            "accepted",
                            "in_progress",
                            "completed",
                            "failed",
                            "delivered",
                        ],
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of tasks to return",
                        "default": 20,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_task",
            "description": "Get detailed information about a specific task by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task ID to look up",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "accept_task",
            "description": "Accept an incoming task. The task must be in pending_accept status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task ID to accept",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "decline_task",
            "description": "Decline an incoming task with an optional reason.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task ID to decline",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for declining",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_agent_profile",
            "description": "Get the full profile of a specific agent by their ID or slug.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "Agent ID or slug to look up",
                    },
                },
                "required": ["agent_id"],
            },
        },
    },
]


class LLMClient:
    """Client for OpenAI-compatible LLM API with Seabay tool support."""

    def __init__(self, config: ShellConfig):
        self.config = config
        self.base_url = config.llm_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {config.llm_api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    def close(self) -> None:
        self._client.close()

    def chat_completion(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> dict:
        """Send a chat completion request with optional tool calling.

        Returns the raw API response dict.
        """
        payload: dict[str, Any] = {
            "model": self.config.llm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        resp = self._client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()

    def get_response(self, messages: list[dict]) -> dict:
        """Get a chat response with Seabay tools available.

        Returns the full choice object including potential tool_calls.
        """
        result = self.chat_completion(messages, tools=SEABAY_TOOLS)
        choices = result.get("choices", [])
        if not choices:
            return {"message": {"role": "assistant", "content": "I could not generate a response."}}
        return choices[0]

    @staticmethod
    def get_system_prompt(agent_info: Optional[dict] = None) -> str:
        """Build the system prompt with optional agent context."""
        prompt = SYSTEM_PROMPT
        if agent_info:
            prompt += f"\n\nCurrent user's agent: {agent_info.get('display_name', 'Unknown')} (@{agent_info.get('slug', '?')})"
            prompt += f"\nAgent type: {agent_info.get('agent_type', '?')}"
            prompt += f"\nAgent ID: {agent_info.get('id', '?')}"
        return prompt

    @staticmethod
    def extract_tool_calls(choice: dict) -> list[dict]:
        """Extract tool calls from a completion choice.

        Returns list of dicts with: id, name, arguments (parsed JSON).
        """
        message = choice.get("message", {})
        raw_calls = message.get("tool_calls", [])
        result = []
        for tc in raw_calls:
            func = tc.get("function", {})
            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            result.append({
                "id": tc.get("id", ""),
                "name": func.get("name", ""),
                "arguments": args,
            })
        return result

    @staticmethod
    def has_tool_calls(choice: dict) -> bool:
        """Check if the choice contains tool calls."""
        message = choice.get("message", {})
        return bool(message.get("tool_calls"))

    @staticmethod
    def get_content(choice: dict) -> str:
        """Extract text content from a choice."""
        message = choice.get("message", {})
        return message.get("content") or ""
