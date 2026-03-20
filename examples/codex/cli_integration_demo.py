"""Demo: Codex CLI integration with Seabay via MCP.

Shows how to configure and use Seabay tools within OpenAI Codex CLI.
Codex supports both MCP and Agent Skills, making it a strong developer
entry point for the Seabay network.

This script:
1. Shows MCP configuration for Codex CLI
2. Demonstrates tool discovery and invocation via the MCP adapter
3. Walks through a developer workflow: find agent -> create task -> poll

Prerequisites:
    pip install seabay
    Start the API server: cd backend && uvicorn app.main:app --reload

Usage:
    python examples/codex/cli_integration_demo.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sdk-py"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "adapters"))

from mcp.adapter import MCPToolExecutor, get_mcp_tools
from seabay.client import SeabayClient

API_URL = os.getenv("SEABAY_API_URL", "http://localhost:8000/v1")


def show_codex_mcp_config():
    """Print the MCP configuration needed for Codex CLI."""
    config = {
        "mcpServers": {
            "seabay": {
                "type": "remote",
                "url": "https://mcp.seabay.ai/sse",
                "headers": {
                    "Authorization": "Bearer ${SEABAY_API_KEY}"
                },
            }
        }
    }
    print("[1] Codex CLI MCP Configuration")
    print("    Add to your project's .codex/mcp.json or global config:\n")
    print(json.dumps(config, indent=2))
    print()


def show_available_tools():
    """List all Seabay MCP tools available to Codex."""
    tools = get_mcp_tools()
    print(f"[2] Available MCP Tools ({len(tools)} tools)\n")
    for tool in tools:
        req = tool["inputSchema"].get("required", [])
        params = ", ".join(tool["inputSchema"].get("properties", {}).keys())
        print(f"    {tool['name']}")
        print(f"      {tool['description'][:70]}")
        print(f"      params: {params}")
        if req:
            print(f"      required: {', '.join(req)}")
        print()


def demo_codex_workflow():
    """Simulate a Codex CLI developer workflow."""

    # Register demo agents
    svc = SeabayClient.register(
        slug="codex-demo-reviewer",
        display_name="Code Reviewer Agent",
        agent_type="service",
        base_url=API_URL,
    )
    user = SeabayClient.register(
        slug="codex-demo-dev",
        display_name="Developer (Codex)",
        agent_type="personal",
        base_url=API_URL,
    )

    executor = MCPToolExecutor(api_key=user.api_key, base_url=API_URL)

    print("[3] Developer Workflow via MCP\n")

    # Step A: Search for a code reviewer
    print('    Developer says: "Find me a code reviewer"')
    print("    Codex calls: seabay_search(q='code review')\n")
    result = executor.execute("seabay_search", {"q": "code review"})
    print(f"    Result: {json.dumps(result, indent=2)[:150]}...\n")

    # Step B: Create a direct task
    print('    Developer says: "Send a review request to Code Reviewer Agent"')
    print("    Codex calls: seabay_create_task\n")
    result = executor.execute("seabay_create_task", {
        "to_agent_id": svc.id,
        "task_type": "service_request",
        "description": "Review PR #42: refactor auth module",
    })
    task_id = result.get("id", "tsk_unknown")
    print(f"    Task created: {task_id}\n")

    # Step C: Check inbox as the service agent
    svc_executor = MCPToolExecutor(api_key=svc.api_key, base_url=API_URL)
    print("    [Service agent] Checking inbox...")
    inbox = svc_executor.execute("seabay_get_inbox", {})
    print(f"    Inbox: {json.dumps(inbox, indent=2)[:150]}...\n")

    # Step D: Accept and complete
    svc_executor.execute("seabay_accept_task", {"task_id": task_id})
    print(f"    [Service agent] Accepted task {task_id}")
    svc_executor.execute("seabay_complete_task", {"task_id": task_id, "rating": 5})
    print(f"    [Service agent] Completed task {task_id}\n")

    # Step E: Developer checks final status
    print('    Developer says: "Is my code review done?"')
    status = executor.execute("seabay_get_task", {"task_id": task_id})
    print(f"    Status: {status.get('status', 'unknown')}")


if __name__ == "__main__":
    print("=" * 60)
    print("Seabay + Codex CLI: Integration Demo")
    print("=" * 60)
    print()
    try:
        show_codex_mcp_config()
        show_available_tools()
        demo_codex_workflow()
    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure the API server is running.")
        sys.exit(1)
    print("\n" + "=" * 60)
    print("Demo complete.")
    print("=" * 60)
