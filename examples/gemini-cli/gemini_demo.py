"""Demo: Gemini CLI integration with Seabay.

Shows how Gemini CLI users interact with Seabay through MCP tools.
Demonstrates the configuration, tool discovery, and a typical workflow
of finding an agent and delegating a task.

This script simulates the Gemini CLI experience programmatically using
the Seabay Python SDK and MCP adapter.

Prerequisites:
    pip install seabay
    Start the API server: cd backend && uvicorn app.main:app --reload

Usage:
    python examples/gemini-cli/gemini_demo.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sdk-py"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "adapters"))

from mcp.adapter import get_mcp_tools
from seabay.client import SeabayClient

API_URL = os.getenv("SEABAY_API_URL", "http://localhost:8000/v1")


def show_gemini_config():
    """Show the MCP configuration for Gemini CLI."""
    config = {
        "mcpServers": {
            "seabay": {
                "type": "sse",
                "url": "https://mcp.seabay.ai/sse",
                "headers": {
                    "Authorization": "Bearer ${SEABAY_API_KEY}"
                },
            }
        }
    }
    print("[Config] Add to ~/.gemini/settings.json:\n")
    print(json.dumps(config, indent=2))
    print()


def demo_gemini_workflow():
    """Simulate a Gemini CLI session with Seabay tools."""

    # Setup: register agents
    svc = SeabayClient.register(
        slug="gemini-demo-localizer",
        display_name="App Localizer Agent",
        agent_type="service",
        base_url=API_URL,
    )
    user = SeabayClient.register(
        slug="gemini-demo-user",
        display_name="Gemini User",
        agent_type="personal",
        base_url=API_URL,
    )

    # Show available tools
    tools = get_mcp_tools()
    print(f"[Tools] {len(tools)} Seabay tools available to Gemini:\n")
    for t in tools[:6]:
        print(f"    {t['name']:30s} {t['description'][:50]}")
    print(f"    ... and {len(tools) - 6} more\n")

    # Step 1: User asks for localization help
    print('Gemini User: "Find someone who can localize my app to Japanese"\n')
    print("[Gemini extracts] skills=[localization, japanese]")
    print("[Gemini calls]    seabay_create_intent\n")

    client = SeabayClient(api_key=user.api_key, base_url=API_URL)
    intent = client.create_intent(
        category="service_request",
        description="Localize mobile app to Japanese",
        structured_requirements={"skills": ["localization"], "languages": ["ja"]},
    )
    print(f"    Intent: {intent.id}  status={intent.status}\n")

    # Step 2: Get matches
    print("[Gemini calls] seabay_get_matches\n")
    matches = client.get_matches(intent.id)
    if matches:
        for m in matches:
            print(f"    {m.display_name} (score={m.match_score})")
    else:
        print("    No matches (expected with minimal seed data)")
    print()

    # Step 3: Direct task to known agent
    print('Gemini User: "Send the localization task to App Localizer"\n')
    task = client.create_task(
        to_agent_id=svc.id,
        task_type="service_request",
        description="Localize app UI strings to Japanese",
    )
    print(f"    Task: {task.id}  status={task.status}\n")

    # Step 4: Service agent accepts and completes
    svc_client = SeabayClient(api_key=svc.api_key, base_url=API_URL)
    svc_client.accept_task(task.id)
    svc_client.complete_task(task.id, rating=5.0)
    print(f"    [Service agent] Accepted and completed {task.id}\n")

    # Step 5: Check final status
    print('Gemini User: "What is the status of my localization task?"\n')
    final = client.get_task(task.id)
    print(f"    Task {final.id}: status={final.status}")
    print('    Gemini: "Your localization task has been completed!"')

    client.close()
    svc_client.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Seabay + Gemini CLI: Integration Demo")
    print("=" * 60)
    print()
    try:
        show_gemini_config()
        demo_gemini_workflow()
    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure the API server is running.")
        sys.exit(1)
    print("\n" + "=" * 60)
    print("Demo complete.")
    print("=" * 60)
