"""Demo: A2A (Agent-to-Agent) Protocol integration with Seabay.

Shows bidirectional conversion between Seabay internal format
and Google A2A specification.

Usage:
    python a2a_integration.py
"""

import json
import sys

sys.path.insert(0, "../adapters")

from a2a.adapter import (
    a2a_card_to_agent,
    a2a_task_to_internal,
    agent_to_a2a_card,
    create_a2a_error,
    create_a2a_message,
    extract_text_from_message,
    internal_state_to_a2a,
    internal_task_to_a2a,
)


def demo_agent_card_conversion():
    """Convert Seabay agent to A2A discovery card and back."""
    print("=" * 60)
    print("Agent → A2A Card Conversion")
    print("=" * 60)
    print()

    agent = {
        "id": "agt_demo123",
        "slug": "smart-translator",
        "display_name": "Smart Translator",
        "agent_type": "service",
        "verification_level": "github",
        "endpoint": "https://translator.example.com/api",
    }
    profile = {
        "bio": "AI-powered translation supporting 50+ languages",
        "skills": ["translation", "localization"],
        "languages": ["en", "zh", "ja"],
    }

    # Seabay → A2A
    a2a_card = agent_to_a2a_card(agent, profile)
    print("A2A Agent Card:")
    print(json.dumps(a2a_card, indent=2))
    print()

    # A2A → Seabay
    restored = a2a_card_to_agent(a2a_card)
    print("Restored Agent Data:")
    print(json.dumps(restored, indent=2))
    print()


def demo_task_conversion():
    """Convert tasks between formats."""
    print("=" * 60)
    print("Task Format Conversion")
    print("=" * 60)
    print()

    internal_task = {
        "id": "tsk_demo456",
        "from_agent_id": "agt_alice",
        "to_agent_id": "agt_translator",
        "task_type": "service_request",
        "description": "Translate README.md from English to Chinese",
        "status": "in_progress",
        "risk_level": "R0",
        "payload_inline": {"source_file": "README.md"},
    }

    # Internal → A2A
    a2a_task = internal_task_to_a2a(internal_task)
    print("A2A Task Format:")
    print(json.dumps(a2a_task, indent=2))
    print()

    # A2A → Internal
    restored = a2a_task_to_internal(a2a_task)
    print("Restored Internal Format:")
    print(json.dumps(restored, indent=2))
    print()


def demo_state_mapping():
    """Show state mapping between Seabay and A2A."""
    print("=" * 60)
    print("State Mapping: Seabay ↔ A2A")
    print("=" * 60)
    print()

    states = [
        "pending_delivery", "delivered", "pending_accept",
        "accepted", "in_progress", "waiting_human_confirm",
        "completed", "declined", "expired", "cancelled", "failed",
    ]

    print(f"{'Seabay':<25} {'A2A State':<20}")
    print("-" * 45)
    for state in states:
        a2a = internal_state_to_a2a(state)
        print(f"{state:<25} {a2a:<20}")
    print()


def demo_messaging():
    """Create A2A messages."""
    print("=" * 60)
    print("A2A Message Creation")
    print("=" * 60)
    print()

    msg = create_a2a_message(
        role="user",
        text="Please translate this document",
    )
    print("Message:")
    print(json.dumps(msg, indent=2))
    print()

    extracted = extract_text_from_message(msg)
    print(f"Extracted text: {extracted}")
    print()

    error = create_a2a_error(
        error_type="authorization_required",
        message="Agent requires verification",
    )
    print("Error:")
    print(json.dumps(error, indent=2))
    print()


if __name__ == "__main__":
    print()
    print("Seabay V1.5 — A2A Protocol Integration Demo")
    print()

    demo_agent_card_conversion()
    demo_task_conversion()
    demo_state_mapping()
    demo_messaging()

    print("=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
