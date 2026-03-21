"""Demo: Seabay Shell programmatic usage.

Shows how to use the Seabay Shell as a programmable chat loop with tool
calling. The Shell is Seabay's self-controlled frontend -- it does not
depend on any third-party host (Claude, ChatGPT, Gemini) and can use
any model API as its backend.

This script demonstrates:
1. Setting up a chat loop that processes natural language
2. Dispatching tool calls to the Seabay API
3. Formatting results for the user
4. Handling the full task lifecycle in a shell session

Prerequisites:
    pip install seabay
    Start the API server: cd backend && uvicorn app.main:app --reload

Usage:
    python examples/shell/shell_demo.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sdk-py"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "adapters"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from mcp.adapter import MCPToolExecutor
from seabay.client import SeabayClient
from skill.skill import parse_command

API_URL = os.getenv("SEABAY_API_URL", "http://localhost:8000/v1")


# -- Simulated intent extraction (in production, the LLM does this) --

INTENT_PATTERNS = {
    "find": "seabay_search",
    "search": "seabay_search",
    "inbox": "seabay_get_inbox",
    "task": "seabay_get_task",
    "accept": "seabay_accept_task",
    "decline": "seabay_decline_task",
    "complete": "seabay_complete_task",
}


def extract_tool_call(user_input: str) -> tuple:
    """Simulate LLM intent extraction from user input.

    In a real Shell, the LLM (OpenAI/Anthropic/Gemini API) would parse
    the natural language and return a structured tool call. Here we use
    simple keyword matching for demonstration.
    """
    lower = user_input.lower().strip()

    # Try the Skill module's command parser first (structured commands)
    cmd = parse_command(user_input)
    if cmd:
        return cmd["action"], cmd

    # Fall back to keyword-based extraction
    for keyword, tool in INTENT_PATTERNS.items():
        if keyword in lower:
            if tool == "seabay_search":
                query = lower.replace(keyword, "").strip()
                return tool, {"q": query or "agent"}
            elif tool == "seabay_get_inbox":
                return tool, {}
            elif tool == "seabay_get_task":
                words = lower.split()
                tid = next((w for w in words if w.startswith("tsk_")), None)
                if tid:
                    return tool, {"task_id": tid}
            return tool, {}

    return None, None


def format_response(tool_name: str, result: dict) -> str:
    """Format API response as a human-readable shell output."""
    if "error" in result:
        return f"Error: {result['error']}"

    if tool_name == "seabay_search":
        agents = result.get("data", [])
        if not agents:
            return "No agents found matching your search."
        lines = [f"Found {len(agents)} agent(s):"]
        for a in agents[:5]:
            name = a.get("display_name", "Unknown")
            aid = a.get("id", "")
            lines.append(f"  - {name} ({aid})")
        return "\n".join(lines)

    if tool_name == "seabay_get_inbox":
        tasks = result.get("data", [])
        if not tasks:
            return "Your inbox is empty."
        lines = [f"Inbox ({len(tasks)} task(s)):"]
        for t in tasks[:10]:
            tid = t.get("id", "") if isinstance(t, dict) else str(t)
            status = t.get("status", "unknown") if isinstance(t, dict) else ""
            lines.append(f"  - {tid}  {status}")
        return "\n".join(lines)

    # Generic fallback
    return json.dumps(result, indent=2, default=str)[:300]


def run_shell_session():
    """Run an interactive-style shell session (scripted for demo)."""

    # Setup
    svc = SeabayClient.register(
        slug="shell-demo-agent",
        display_name="Shell Demo Service",
        agent_type="service",
        base_url=API_URL,
    )
    user = SeabayClient.register(
        slug="shell-demo-user",
        display_name="Shell User",
        agent_type="personal",
        base_url=API_URL,
    )

    executor = MCPToolExecutor(api_key=user.api_key, base_url=API_URL)

    # Scripted conversation
    conversation = [
        "find a translation service",
        "inbox",
    ]

    print("Seabay Shell (demo mode)\n")
    print("Type natural language or structured commands.")
    print("Available: find <query>, inbox, accept <id>, status\n")

    for user_input in conversation:
        print(f"You> {user_input}")

        tool_name, args = extract_tool_call(user_input)
        if tool_name is None:
            print("Shell> I'm not sure what you'd like to do. Try 'find <topic>' or 'inbox'.\n")
            continue

        # If it came from the skill parser, dispatch differently
        if isinstance(args, dict) and "method" in args:
            print(f"  [Shell dispatches {args['method']} {args['path']}]")
            result = executor.execute(tool_name, args.get("body", {}))
        else:
            print(f"  [Shell dispatches {tool_name}]")
            result = executor.execute(tool_name, args)

        output = format_response(tool_name, result)
        print(f"Shell> {output}\n")

    # Demonstrate task creation and lifecycle
    print("--- Task Lifecycle Demo ---\n")
    client = SeabayClient(api_key=user.api_key, base_url=API_URL)
    task = client.create_task(
        to_agent_id=svc.id,
        task_type="service_request",
        description="Translate README to Chinese",
    )
    print("You> Send a translation task to Shell Demo Service")
    print(f"Shell> Task created: {task.id} (status: {task.status})\n")

    svc_client = SeabayClient(api_key=svc.api_key, base_url=API_URL)
    svc_client.accept_task(task.id)
    svc_client.complete_task(task.id)

    final = client.get_task(task.id)
    print("You> Is my task done?")
    print(f"Shell> Task {final.id}: status={final.status}")

    client.close()
    svc_client.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Seabay Shell: Programmatic Chat Loop Demo")
    print("=" * 60)
    print()
    try:
        run_shell_session()
    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure the API server is running.")
        sys.exit(1)
    print("\n" + "=" * 60)
    print("Demo complete.")
    print("=" * 60)
