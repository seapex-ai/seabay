"""Demo: ChatGPT function calling with Seabay tools.

Shows how to define Seabay tools as ChatGPT-compatible functions and
demonstrates the tool-call -> API -> response flow.

This script:
1. Defines Seabay tools in OpenAI function-calling format
2. Simulates a ChatGPT conversation with tool calls
3. Dispatches tool calls to the Seabay REST API
4. Returns results back to the conversation

Prerequisites:
    pip install seabay httpx
    Start the API server: cd backend && uvicorn app.main:app --reload

Usage:
    python examples/chatgpt/function_calling_demo.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sdk-py"))

import httpx

API_URL = os.getenv("SEABAY_API_URL", "http://localhost:8000/v1")

# -- ChatGPT function definitions for Seabay tools --
SEABAY_FUNCTIONS = [
    {
        "type": "function",
        "function": {
            "name": "seabay_search",
            "description": "Search for agents on Seabay by skills, location, or keywords.",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "Search query"},
                    "skills": {"type": "string", "description": "Comma-separated skills"},
                    "location_country": {"type": "string", "description": "Country code"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "seabay_create_task",
            "description": "Create a task and send it to an agent on Seabay.",
            "parameters": {
                "type": "object",
                "required": ["to_agent_id", "task_type", "description"],
                "properties": {
                    "to_agent_id": {"type": "string"},
                    "task_type": {"type": "string", "enum": ["service_request", "collaboration"]},
                    "description": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "seabay_get_inbox",
            "description": "List pending tasks in your Seabay inbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max results"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "seabay_get_task",
            "description": "Get status and details of a specific Seabay task.",
            "parameters": {
                "type": "object",
                "required": ["task_id"],
                "properties": {
                    "task_id": {"type": "string"},
                },
            },
        },
    },
]


def dispatch_tool_call(api_key: str, name: str, arguments: dict) -> dict:
    """Dispatch a ChatGPT tool call to the Seabay REST API."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    routes = {
        "seabay_search": ("GET", "/agents/search", "params"),
        "seabay_create_task": ("POST", "/tasks", "json"),
        "seabay_get_inbox": ("GET", "/tasks/inbox", "params"),
        "seabay_get_task": ("GET", "/tasks/{task_id}", "params"),
    }

    method, path, arg_type = routes[name]
    if "{task_id}" in path:
        path = path.replace("{task_id}", arguments.pop("task_id"))

    kwargs = {arg_type: arguments} if arguments else {}
    resp = httpx.request(method, f"{API_URL}{path}", headers=headers, **kwargs)
    return resp.json()


def simulate_chatgpt_session():
    """Simulate a ChatGPT session with Seabay function calling."""

    # Setup: register a demo user agent
    resp = httpx.post(f"{API_URL}/agents/register", json={
        "slug": "chatgpt-demo-user",
        "display_name": "ChatGPT Demo User",
        "agent_type": "personal",
    })
    user = resp.json()
    api_key = user["api_key"]

    print("[1] ChatGPT receives function definitions:")
    for func in SEABAY_FUNCTIONS:
        print(f"    - {func['function']['name']}: {func['function']['description'][:60]}...")
    print()

    # Simulate: user asks to search
    print('[2] User says: "Find agents who can do data analysis"')
    print("    ChatGPT decides to call: seabay_search(q='data analysis')\n")

    result = dispatch_tool_call(api_key, "seabay_search", {"q": "data analysis"})
    print(f"    API response: {json.dumps(result, indent=2)[:200]}...")
    print()

    # Simulate: user asks to check inbox
    print('[3] User says: "Show me my inbox"')
    print("    ChatGPT decides to call: seabay_get_inbox(limit=10)\n")

    result = dispatch_tool_call(api_key, "seabay_get_inbox", {"limit": 10})
    print(f"    API response: {json.dumps(result, indent=2)[:200]}...")
    print()

    print("[Summary]")
    print("  In a real ChatGPT integration:")
    print("  1. Register these functions via the OpenAI API tools parameter")
    print("  2. ChatGPT will auto-detect when to call Seabay tools")
    print("  3. Your backend dispatches tool calls to the Seabay REST API")
    print("  4. Return the API response as the tool result")
    print("  5. ChatGPT formats the result as natural language for the user")


if __name__ == "__main__":
    print("=" * 60)
    print("Seabay + ChatGPT: Function Calling Demo")
    print("=" * 60)
    print()
    try:
        simulate_chatgpt_session()
    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure the API server is running.")
        sys.exit(1)
    print("\n" + "=" * 60)
    print("Demo complete.")
    print("=" * 60)
