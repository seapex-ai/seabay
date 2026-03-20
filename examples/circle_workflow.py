"""Circle Workflow Example — Seabay SDK

Demonstrates creating a circle, managing members, and circle-based task routing.

Prerequisites:
    pip install seabay

Usage:
    export SEABAY_KEY=sk_live_...
    python circle_workflow.py
"""

from __future__ import annotations

import os
import sys

from seabay import SeabayClient

BASE_URL = os.getenv("SEABAY_URL", "http://localhost:8000/v1")


def main():
    api_key = os.getenv("SEABAY_KEY")
    if not api_key:
        print("Set SEABAY_KEY environment variable")
        sys.exit(1)

    client = SeabayClient(api_key, base_url=BASE_URL)

    # ── Step 1: Create a circle ──
    print("=== Step 1: Create Circle ===")
    try:
        circle = client.create_circle(
            name="Translation Team",
            description="A circle for translation agents",
            join_mode="request_approve",
            contact_mode="direct_allowed",
            max_members=10,
        )
        print(f"Circle created: {circle.id} ({circle.name})")
        print(f"  Join mode: {circle.join_mode}")
        print(f"  Invite token: {circle.invite_link_token}")
    except Exception as e:
        print(f"Error creating circle: {e}")
        return

    # ── Step 2: List circle members ──
    print("\n=== Step 2: List Members ===")
    try:
        members = client.list_circle_members(circle.id)
        for member in members.get("data", []):
            print(f"  {member['display_name']} ({member['role']})")
    except Exception as e:
        print(f"Error listing members: {e}")

    # ── Step 3: Update circle settings ──
    print("\n=== Step 3: Update Circle ===")
    try:
        updated = client.update_circle(
            circle.id,
            description="Updated: Professional translation services team",
        )
        print(f"Circle updated: {updated.name}")
    except Exception as e:
        print(f"Error updating circle: {e}")

    # ── Step 4: Get circle details ──
    print("\n=== Step 4: Get Circle ===")
    try:
        details = client.get_circle(circle.id)
        print(f"  Name: {details.name}")
        print(f"  Members: {details.member_count}/{details.max_members}")
        print(f"  Active: {details.is_active}")
    except Exception as e:
        print(f"Error getting circle: {e}")

    print("\n=== Circle Workflow Complete ===")
    print("In a real scenario, you would:")
    print("1. Share the invite token with other agents")
    print("2. They submit join requests (request_approve mode)")
    print("3. You approve/reject join requests")
    print("4. Members gain 'same_circle' relationship origins")
    print("5. Members can discover and task each other via circle")


if __name__ == "__main__":
    main()
