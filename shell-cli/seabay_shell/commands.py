"""Built-in slash commands for Seabay Shell."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Optional

import httpx

if TYPE_CHECKING:
    from seabay_shell.config import ShellConfig
    from seabay_shell.renderer import TerminalRenderer


class SeabayAPI:
    """Thin API client used by both commands and LLM tool execution."""

    def __init__(self, config: ShellConfig):
        self.config = config
        self.base_url = config.api_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        resp = self._client.request(method, path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    # ── Agent ──

    def get_my_agent(self) -> dict:
        return self._request("GET", "/agents/me")

    def get_agent(self, agent_id: str) -> dict:
        return self._request("GET", f"/agents/{agent_id}")

    def search_agents(self, **params: Any) -> dict:
        return self._request("GET", "/agents/search", params=params)

    def get_public_agent(self, slug: str) -> dict:
        return self._request("GET", f"/public/agents/{slug}")

    # ── Tasks ──

    def create_task(self, to_agent_id: str, task_type: str = "service_request",
                    description: str = "", **kwargs: Any) -> dict:
        body = {
            "to_agent_id": to_agent_id,
            "task_type": task_type,
            "description": description,
            "idempotency_key": f"shell-{int(time.time() * 1000)}",
            **kwargs,
        }
        return self._request("POST", "/tasks", json=body)

    def get_task(self, task_id: str) -> dict:
        return self._request("GET", f"/tasks/{task_id}")

    def get_inbox(self, **params: Any) -> dict:
        return self._request("GET", "/tasks/inbox", params=params)

    def accept_task(self, task_id: str) -> dict:
        return self._request("POST", f"/tasks/{task_id}/accept")

    def decline_task(self, task_id: str, reason: Optional[str] = None) -> dict:
        return self._request("POST", f"/tasks/{task_id}/decline", json={"reason": reason})

    def complete_task(self, task_id: str, **kwargs: Any) -> dict:
        return self._request("POST", f"/tasks/{task_id}/complete", json=kwargs)

    # ── Health ──

    def health(self) -> dict:
        return self._request("GET", "/health")


# ── Tool executor (bridges LLM tool calls to API) ──

def execute_tool(api: SeabayAPI, tool_name: str, args: dict) -> str:
    """Execute a Seabay tool call and return the result as a JSON string."""
    try:
        if tool_name == "search_agents":
            params = {}
            if args.get("q"):
                params["q"] = args["q"]
            if args.get("skills"):
                params["skills"] = args["skills"]
            if args.get("location"):
                params["location"] = args["location"]
            if args.get("language"):
                params["language"] = args["language"]
            if args.get("agent_type"):
                params["agent_type"] = args["agent_type"]
            result = api.search_agents(**params)
            return json.dumps(result, default=str)

        elif tool_name == "create_task":
            result = api.create_task(
                to_agent_id=args["to_agent_id"],
                task_type=args.get("task_type", "service_request"),
                description=args.get("description", ""),
            )
            return json.dumps(result, default=str)

        elif tool_name == "check_inbox":
            params = {}
            if args.get("status"):
                params["status"] = args["status"]
            if args.get("limit"):
                params["limit"] = str(args["limit"])
            result = api.get_inbox(**params)
            return json.dumps(result, default=str)

        elif tool_name == "get_task":
            result = api.get_task(args["task_id"])
            return json.dumps(result, default=str)

        elif tool_name == "accept_task":
            result = api.accept_task(args["task_id"])
            return json.dumps(result, default=str)

        elif tool_name == "decline_task":
            result = api.decline_task(args["task_id"], reason=args.get("reason"))
            return json.dumps(result, default=str)

        elif tool_name == "get_agent_profile":
            agent_id = args["agent_id"]
            try:
                result = api.get_agent(agent_id)
            except httpx.HTTPStatusError:
                # Try as slug via public endpoint
                result = api.get_public_agent(agent_id)
            return json.dumps(result, default=str)

        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

    except httpx.HTTPStatusError as e:
        error_body = e.response.text
        return json.dumps({"error": f"API error {e.response.status_code}: {error_body}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Slash command handler ──

HELP_TEXT = """
Available commands:

  /help                — Show this help message
  /status              — Show current agent status and server health
  /inbox               — List inbox tasks
  /search <query>      — Search for agents
  /task <id>           — Get task details
  /accept <id>         — Accept a task
  /decline <id>        — Decline a task
  /connect <slug>      — View an agent's profile
  /clear               — Clear chat history
  /config              — Show current configuration
  /quit                — Exit the shell

Or just type naturally! The AI will help you find agents, create tasks, and more.
"""


def handle_command(
    command: str,
    api: SeabayAPI,
    renderer: TerminalRenderer,
    config: Optional[Any] = None,
) -> Optional[str]:
    """Handle a slash command. Returns None to continue, 'quit' to exit.

    Returns a string result for commands that produce output, or None.
    """
    parts = command.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "/help":
        renderer.render_text(HELP_TEXT)
        return "handled"

    elif cmd == "/quit" or cmd == "/exit":
        return "quit"

    elif cmd == "/clear":
        renderer.render_info("Chat history cleared.")
        return "clear"

    elif cmd == "/status":
        try:
            agent = api.get_my_agent()
            try:
                health = api.health()
            except Exception:
                health = None
            renderer.render_status(agent, health)
        except httpx.HTTPStatusError as e:
            renderer.render_error(f"Failed to get status: {e.response.text}")
        except httpx.ConnectError:
            renderer.render_error(f"Cannot connect to {api.base_url}")
        return "handled"

    elif cmd == "/inbox":
        try:
            params = {}
            if arg:
                params["status"] = arg
            result = api.get_inbox(**params)
            tasks = result.get("data", [])
            renderer.render_inbox(tasks, result.get("has_more", False))
        except httpx.HTTPStatusError as e:
            renderer.render_error(f"Failed to get inbox: {e.response.text}")
        return "handled"

    elif cmd == "/search":
        if not arg:
            renderer.render_error("Usage: /search <query>")
            return "handled"
        try:
            result = api.search_agents(q=arg)
            agents = result.get("data", [])
            renderer.render_match_results(agents, f"Search results for '{arg}':")
        except httpx.HTTPStatusError as e:
            renderer.render_error(f"Search failed: {e.response.text}")
        return "handled"

    elif cmd == "/task":
        if not arg:
            renderer.render_error("Usage: /task <task_id>")
            return "handled"
        try:
            task = api.get_task(arg)
            renderer.render_task(task)
        except httpx.HTTPStatusError as e:
            renderer.render_error(f"Failed to get task: {e.response.text}")
        return "handled"

    elif cmd == "/accept":
        if not arg:
            renderer.render_error("Usage: /accept <task_id>")
            return "handled"
        try:
            task = api.accept_task(arg)
            renderer.render_success(f"Task {arg} accepted -> {task.get('status', 'accepted')}")
        except httpx.HTTPStatusError as e:
            renderer.render_error(f"Failed to accept task: {e.response.text}")
        return "handled"

    elif cmd == "/decline":
        if not arg:
            renderer.render_error("Usage: /decline <task_id>")
            return "handled"
        try:
            task = api.decline_task(arg)
            renderer.render_success(f"Task {arg} declined -> {task.get('status', 'declined')}")
        except httpx.HTTPStatusError as e:
            renderer.render_error(f"Failed to decline task: {e.response.text}")
        return "handled"

    elif cmd == "/connect":
        if not arg:
            renderer.render_error("Usage: /connect <agent_slug_or_id>")
            return "handled"
        try:
            try:
                agent = api.get_public_agent(arg)
            except httpx.HTTPStatusError:
                agent = api.get_agent(arg)
            renderer.render_agent(agent)
        except httpx.HTTPStatusError as e:
            renderer.render_error(f"Agent not found: {e.response.text}")
        return "handled"

    elif cmd == "/config":
        if config:
            renderer.render_info(f"API URL:   {config.api_url}")
            renderer.render_info(f"LLM URL:   {config.llm_url}")
            renderer.render_info(f"LLM Model: {config.llm_model}")
            renderer.render_info(f"Agent ID:  {config.agent_id or 'not set'}")
            renderer.render_info(f"Agent:     {config.agent_name or 'not set'}")
            renderer.render_info(f"LLM:       {'configured' if config.has_llm else 'not configured'}")
        return "handled"

    else:
        renderer.render_error(f"Unknown command: {cmd}. Type /help for available commands.")
        return "handled"
