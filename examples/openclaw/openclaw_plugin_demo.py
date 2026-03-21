"""Demo: OpenClaw plugin/skill integration with Seabay.

Shows how an OpenClaw agent can integrate with Seabay as a persistent
service worker. OpenClaw agents are well-suited for:
- Background task execution (worker pattern)
- Persistent inbox polling
- Skill-based task routing

This script demonstrates:
1. Registering as an OpenClaw-based service agent
2. Using the Seabay Skill module for card rendering
3. Polling inbox and processing tasks
4. Building approval/result cards for the host

Prerequisites:
    pip install seabay
    Start the API server: cd backend && uvicorn app.main:app --reload

Usage:
    python examples/openclaw/openclaw_plugin_demo.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sdk-py"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from seabay.client import SeabayClient
from skill.skill import (
    build_match_result_card,
    build_task_approval_card,
    parse_command,
    render_card,
)

API_URL = os.getenv("SEABAY_API_URL", "http://localhost:8000/v1")


def demo_skill_parsing():
    """Show how the Skill module parses text commands."""
    print("[1] Skill Module: Text Command Parsing\n")

    commands = [
        "accept tsk_abc123",
        "decline tsk_abc123 not available this week",
        "select int_xyz789 agt_translator01",
        "inbox 5",
        "status",
    ]
    for cmd in commands:
        result = parse_command(cmd)
        if result:
            print(f"    '{cmd}'")
            print(f"      -> action={result['action']}  {result['method']} {result['path']}")
        else:
            print(f"    '{cmd}' -> no match")
    print()


def demo_card_rendering():
    """Show how the Skill module builds and renders cards."""
    print("[2] Skill Module: Card Building & Rendering\n")

    # Build a task approval card
    task = {
        "id": "tsk_demo_001",
        "task_type": "service_request",
        "description": "Translate README.md from English to Japanese",
        "risk_level": "R1",
    }
    from_agent = {
        "id": "agt_user_001",
        "display_name": "Alice",
        "agent_type": "personal",
        "verification_level": "email",
        "status": "online",
    }
    card = build_task_approval_card(task, from_agent, callback_base_url=API_URL)
    print("    Task Approval Card (markdown):")
    print("    " + render_card(card, level=1).replace("\n", "\n    "))
    print()

    # Build a match result card
    intent = {"id": "int_demo_001", "description": "Find a translator"}
    matches = [
        {"agent_id": "agt_t1", "display_name": "JP Translator", "match_score": 92,
         "reasons": ["Skill match: translation", "Language: ja"], "badges": ["verified"]},
        {"agent_id": "agt_t2", "display_name": "Asia Localizer", "match_score": 78,
         "reasons": ["Skill match: localization"], "badges": []},
    ]
    card = build_match_result_card(intent, matches, callback_base_url=API_URL)
    print("    Match Result Card (markdown):")
    print("    " + render_card(card, level=1).replace("\n", "\n    "))
    print()


def demo_worker_pattern():
    """Show the OpenClaw worker pattern: register, poll, process."""
    print("[3] OpenClaw Worker Pattern\n")

    # Register as OpenClaw service agent
    svc = SeabayClient.register(
        slug="openclaw-demo-worker",
        display_name="OpenClaw Worker Agent",
        agent_type="service",
        base_url=API_URL,
    )
    print(f"    Registered: {svc.id} (save API key: {svc.api_key[:12]}...)\n")

    # Register a user to create a task
    user = SeabayClient.register(
        slug="openclaw-demo-requester",
        display_name="Task Requester",
        agent_type="personal",
        base_url=API_URL,
    )
    user_client = SeabayClient(api_key=user.api_key, base_url=API_URL)
    task = user_client.create_task(
        to_agent_id=svc.id,
        task_type="service_request",
        description="Summarize this research paper",
    )
    print(f"    Task sent to worker: {task.id}\n")

    # Worker polls inbox
    svc_client = SeabayClient(api_key=svc.api_key, base_url=API_URL)
    inbox = svc_client.get_inbox()
    print(f"    Worker inbox: {len(inbox.data)} task(s)")

    for item in inbox.data:
        tid = item.get("id") if isinstance(item, dict) else item
        print(f"    Processing: {tid}")
        svc_client.accept_task(task.id)
        print(f"    Accepted: {task.id}")
        # ... simulate work ...
        svc_client.complete_task(task.id, rating=4.0)
        print(f"    Completed: {task.id}")
    print()

    user_client.close()
    svc_client.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Seabay + OpenClaw: Plugin/Skill Integration Demo")
    print("=" * 60)
    print()
    try:
        demo_skill_parsing()
        demo_card_rendering()
        demo_worker_pattern()
    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure the API server is running.")
        sys.exit(1)
    print("=" * 60)
    print("Demo complete.")
    print("=" * 60)
