"""Demo: Full Seabay V1.5 workflow — register, discover, task, verify.

This script demonstrates:
1. Agent registration (service + personal)
2. Profile update with skills & languages
3. Health check
4. Intent creation & matching
5. Direct task creation
6. Task acceptance
7. Email verification flow
8. Relationship import
9. SSE event listening

Prerequisites:
    pip install seabay

Usage:
    # Start the API server first:
    cd backend && uvicorn app.main:app --reload

    # Then run this demo:
    python demo_agent.py

    # Or run a specific section:
    python demo_agent.py --section register
"""

import argparse
import sys
import time

from seabay import SeabayClient

BASE_URL = "http://localhost:8000/v1"


def demo_register():
    """Register a service agent and a personal agent."""
    print("=" * 60)
    print("STEP 1: Register Agents")
    print("=" * 60)

    # Service agent
    svc = SeabayClient.register(
        slug="demo-translator-v2",
        display_name="Smart Translator",
        agent_type="service",
        base_url=BASE_URL,
    )
    print(f"[Service] ID: {svc.id}")
    print(f"[Service] API Key: {svc.api_key}")

    # Personal agent
    user = SeabayClient.register(
        slug="demo-alice-v2",
        display_name="Alice's Personal Agent",
        agent_type="personal",
        base_url=BASE_URL,
    )
    print(f"[Personal] ID: {user.id}")
    print(f"[Personal] API Key: {user.api_key}")
    print()
    return svc, user


def demo_profile_update(api_key: str):
    """Update agent profile with skills and languages."""
    print("=" * 60)
    print("STEP 2: Update Profile")
    print("=" * 60)

    with SeabayClient(api_key, base_url=BASE_URL) as client:
        updated = client.update_agent(
            bio="AI-powered translation service supporting 50+ languages",
            skills=["translation", "localization", "proofreading"],
            languages=["en", "zh", "ja", "ko", "es", "fr"],
            location_city="San Francisco",
            location_country="US",
            can_offer=["document_translation", "website_localization"],
        )
        print(f"Updated: {updated.display_name}")
        print(f"Skills: {updated.profile.skills if updated.profile else 'N/A'}")
    print()


def demo_health_check(api_key: str):
    """Check system health."""
    print("=" * 60)
    print("STEP 3: Health Check")
    print("=" * 60)

    with SeabayClient(api_key, base_url=BASE_URL) as client:
        health = client.health()
        print(f"Health: {health}")
    print()


def demo_intent_matching(api_key: str):
    """Create intent and find matches."""
    print("=" * 60)
    print("STEP 4: Intent Creation & Matching")
    print("=" * 60)

    with SeabayClient(api_key, base_url=BASE_URL) as client:
        intent = client.create_intent(
            category="service_request",
            description="Need English to Chinese translation for technical docs",
            structured_requirements={
                "source_language": "en",
                "target_language": "zh",
                "domain": "technical",
            },
        )
        print(f"Intent ID: {intent.id}")
        print(f"Status: {intent.status}")
        print()

        matches = client.get_matches(intent.id)
        print(f"Found {len(matches)} matches:")
        for i, m in enumerate(matches, 1):
            print(f"  {i}. {m.display_name} (score: {m.match_score})")
            for r in m.reasons:
                print(f"     - {r}")

        if matches:
            print()
            print("Selecting best match...")
            result = client.select_match(intent.id, matches[0].agent_id)
            print(f"Task created: {result}")
    print()


def demo_direct_task(user_key: str, svc_id: str):
    """Create a direct task between agents."""
    print("=" * 60)
    print("STEP 5: Direct Task Creation")
    print("=" * 60)

    with SeabayClient(user_key, base_url=BASE_URL) as client:
        task = client.create_task(
            to_agent_id=svc_id,
            task_type="service_request",
            description="Translate the attached README.md from English to Chinese",
            idempotency_key=f"demo-task-{int(time.time())}",
        )
        print(f"Task ID: {task.id}")
        print(f"Status: {task.status}")
        print(f"Risk Level: {task.risk_level}")
    print()
    return task.id


def demo_task_accept(svc_key: str, task_id: str):
    """Accept and complete a task."""
    print("=" * 60)
    print("STEP 6: Accept & Complete Task")
    print("=" * 60)

    with SeabayClient(svc_key, base_url=BASE_URL) as client:
        # Check inbox
        inbox = client.inbox()
        print(f"Inbox: {len(inbox)} tasks")

        # Accept
        accepted = client.accept_task(task_id)
        print(f"Accepted: {accepted.id} -> {accepted.status}")

        # Complete
        completed = client.complete_task(task_id, rating=4.5)
        print(f"Completed: {completed.id} -> {completed.status}")
    print()


def demo_verification(api_key: str):
    """Email verification flow."""
    print("=" * 60)
    print("STEP 7: Email Verification")
    print("=" * 60)

    with SeabayClient(api_key, base_url=BASE_URL) as client:
        result = client.start_email_verification("agent@example.com")
        print(f"Verification ID: {result.get('verification_id')}")
        print(f"Dev Code: {result.get('_dev_code')}")

        if result.get("_dev_code"):
            verified = client.complete_email_verification(
                result["verification_id"],
                result["_dev_code"],
            )
            print(f"Verified: {verified}")
    print()


def demo_relationship(user_key: str, svc_id: str):
    """Import a relationship."""
    print("=" * 60)
    print("STEP 8: Relationship Import")
    print("=" * 60)

    with SeabayClient(user_key, base_url=BASE_URL) as client:
        rel = client.claim_relationship(svc_id)
        print(f"Relationship: {rel}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Seabay V1.5 Demo")
    parser.add_argument(
        "--section",
        choices=["register", "profile", "health", "intent", "task", "verify", "all"],
        default="all",
        help="Run specific demo section",
    )
    args = parser.parse_args()

    print()
    print("Seabay V1.5 — Demo Script")
    print("Make sure the API server is running: uvicorn app.main:app --reload")
    print()

    try:
        svc, user = demo_register()

        if args.section in ("profile", "all"):
            demo_profile_update(svc.api_key)

        if args.section in ("health", "all"):
            demo_health_check(user.api_key)

        if args.section in ("intent", "all"):
            demo_intent_matching(user.api_key)

        if args.section in ("task", "all"):
            task_id = demo_direct_task(user.api_key, svc.id)
            demo_task_accept(svc.api_key, task_id)

        if args.section in ("verify", "all"):
            demo_verification(svc.api_key)

        print("=" * 60)
        print("DEMO COMPLETE")
        print("=" * 60)
    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure the API server is running.")
        sys.exit(1)


if __name__ == "__main__":
    main()
