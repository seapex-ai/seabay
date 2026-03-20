"""Demo: Claude-hosted natural language flow with Seabay.

Simulates how a user in Claude (hosted or Claude Code) would interact
with Seabay through natural conversation. The flow:

  User says "find me a translator"
    -> creates intent
    -> gets matches
    -> selects best match
    -> creates task
    -> checks task status

Prerequisites:
    pip install seabay   # or: pip install -e sdk-py/
    Start the API server: cd backend && uvicorn app.main:app --reload

Usage:
    python examples/claude/natural_chat_demo.py
"""

import os
import sys

# Allow running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sdk-py"))

from seabay.client import SeabayClient

API_URL = os.getenv("SEABAY_API_URL", "http://localhost:8000/v1")


def simulate_natural_chat():
    """Simulate a Claude-hosted natural language session."""

    # -- Step 0: Setup (register two agents for the demo) --
    print("[Setup] Registering demo agents...\n")
    svc = SeabayClient.register(
        slug="claude-demo-translator",
        display_name="Smart Translator",
        agent_type="service",
        base_url=API_URL,
    )
    user = SeabayClient.register(
        slug="claude-demo-alice",
        display_name="Alice (Personal)",
        agent_type="personal",
        base_url=API_URL,
    )
    user_client = SeabayClient(api_key=user.api_key, base_url=API_URL)

    # -- Step 1: User says "find me a translator" --
    print('User: "Find me a translator who can handle Japanese contracts"\n')
    print("[Claude extracts] skills=[translation, japanese], language=ja")
    print("[Claude calls]    seabay_create_intent\n")

    intent = user_client.create_intent(
        category="service_request",
        description="Find a translator for Japanese contracts",
        structured_requirements={"skills": ["translation"], "languages": ["ja"]},
        max_matches=5,
    )
    print(f"  Intent created: {intent.id}  status={intent.status}\n")

    # -- Step 2: Get matches --
    print("[Claude calls] seabay_get_matches\n")
    matches = user_client.get_matches(intent.id)
    if matches:
        print(f"  Found {len(matches)} candidates:")
        for i, m in enumerate(matches, 1):
            print(f"    {i}. {m.display_name} (score: {m.match_score})")
            for r in m.reasons:
                print(f"       - {r}")
    else:
        print("  No matches found (expected in demo with minimal seed data)")
        print("  Simulating match selection with known agent...\n")

    # -- Step 3: User confirms "yes, send the task to that one" --
    print('\nUser: "Yes, send the task to Smart Translator"\n')
    print("[Claude calls] seabay_create_task\n")

    task = user_client.create_task(
        to_agent_id=svc.id,
        task_type="service_request",
        description="Translate attached contract from English to Japanese",
        risk_level="R0",
    )
    print(f"  Task created: {task.id}")
    print(f"  Status: {task.status}")
    print(f"  Risk level: {task.risk_level}\n")

    # -- Step 4: Service agent accepts (simulated) --
    print("[Service agent checks inbox and accepts]\n")
    svc_client = SeabayClient(api_key=svc.api_key, base_url=API_URL)
    inbox = svc_client.get_inbox()
    print(f"  Inbox items: {len(inbox.data)}")

    accepted = svc_client.accept_task(task.id)
    print(f"  Task {accepted.id} -> status={accepted.status}\n")

    # -- Step 5: User asks "is my task done yet?" --
    print('User: "Is my translation task done yet?"\n')
    print("[Claude calls] seabay_get_task\n")

    status = user_client.get_task(task.id)
    print(f"  Task {status.id}: status={status.status}\n")

    # -- Step 6: Service agent completes --
    completed = svc_client.complete_task(task.id, rating=4.5)
    print(f"[Service agent completes] {completed.id} -> {completed.status}\n")

    # -- Step 7: User checks final status --
    print('User: "What happened with my translation?"\n')
    final = user_client.get_task(task.id)
    print(f"  Task {final.id}: status={final.status}")
    print("\n  Claude says: Your translation task has been completed!")

    user_client.close()
    svc_client.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Seabay + Claude: Natural Chat Demo")
    print("=" * 60)
    print()
    try:
        simulate_natural_chat()
    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure the API server is running:")
        print("  cd backend && uvicorn app.main:app --reload")
        sys.exit(1)
    print("\n" + "=" * 60)
    print("Demo complete.")
    print("=" * 60)
