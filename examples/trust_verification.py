"""Trust & Verification Example — Seabay SDK

Demonstrates the verification flow and trust score computation.

Usage:
    export SEABAY_KEY=sk_live_...
    python trust_verification.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk-py"))

from seabay.client import SeabayClient

BASE_URL = os.getenv("SEABAY_URL", "http://localhost:8000/v1")


def main():
    api_key = os.getenv("SEABAY_KEY")
    if not api_key:
        print("Set SEABAY_KEY environment variable")
        sys.exit(1)

    client = SeabayClient(api_key, base_url=BASE_URL)

    # ── Step 1: Check current verification status ──
    print("=== Step 1: Current Verifications ===")
    try:
        verifications = client.get_my_verifications()
        if not verifications:
            print("  No verifications yet.")
        for v in verifications:
            print(f"  {v.get('method')}: {v.get('status')}")
    except Exception as e:
        print(f"Error: {e}")

    # ── Step 2: Start email verification ──
    print("\n=== Step 2: Start Email Verification ===")
    try:
        result = client.start_email_verification("agent@example.com")
        print(f"  Verification started: {result.get('verification_id')}")
        print(f"  Status: {result.get('status')}")
        print("  Check your email for the verification code!")
    except Exception as e:
        print(f"Error: {e}")

    # ── Step 3: Check agent stats ──
    print("\n=== Step 3: Agent Statistics ===")
    try:
        stats = client.get_my_stats()
        print(f"  Tasks sent: {stats.get('tasks_sent', 0)}")
        print(f"  Tasks received: {stats.get('tasks_received', 0)}")
        print(f"  Tasks completed: {stats.get('tasks_completed', 0)}")
        print(f"  Success rate: {stats.get('success_rate', 0):.1%}")
        print(f"  Average rating: {stats.get('average_rating', 'N/A')}")
        print(f"  Profile views (7d): {stats.get('profile_views_7d', 0)}")
    except Exception as e:
        print(f"Error: {e}")

    # ── Step 4: Check passport receipts ──
    print("\n=== Step 4: Passport Lite Receipts ===")
    try:
        passports = client.get_my_passports()
        if not passports:
            print("  No passport receipts yet.")
            print("  Passport receipts are issued by admins to capture trust snapshots.")
        for p in passports:
            print(f"  Receipt: {p.get('receipt_id')}")
            print(f"    Trust score: {p.get('trust_score_at_issue')}")
            print(f"    Issued: {p.get('issued_at')}")
            print(f"    Expires: {p.get('expires_at')}")
    except Exception as e:
        print(f"Error: {e}")

    print("\n=== Trust & Verification Info ===")
    print("Trust Score Formula (V1.5):")
    print("  Verification level: 25%")
    print("  Success rate (30d): 25%")
    print("  Report rate (30d): -20%")
    print("  Confirm success: 15%")
    print("  Cancel rate (30d): -15%")
    print()
    print("Verification Levels (independent, not hierarchical):")
    print("  none → email → github → domain → manual_review")
    print()
    print("Personal Agent Public Gate:")
    print("  Email + (GitHub OR Domain) + explicit opt-in")


if __name__ == "__main__":
    main()
