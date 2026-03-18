"""Webhook Setup Example — Seabay SDK

Demonstrates configuring webhook endpoints for receiving task notifications.

Prerequisites:
    pip install seabay

Usage:
    export SEABAY_KEY=sk_live_...
    python webhook_setup.py
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

BASE_URL = os.getenv("SEABAY_URL", "http://localhost:8000/v1")
WEBHOOK_PORT = 9999


class WebhookHandler(BaseHTTPRequestHandler):
    """Simple webhook receiver for demonstration."""

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Check for HMAC signature
        signature = self.headers.get("X-Seabay-Signature")
        event_type = self.headers.get("X-Seabay-Event")

        print("\n📨 Webhook received!")
        print(f"   Event: {event_type}")
        if signature:
            print(f"   Signature: {signature[:20]}...")

        try:
            payload = json.loads(body)
            print(f"   Payload: {json.dumps(payload, indent=2)[:200]}")
        except json.JSONDecodeError:
            print(f"   Raw body: {body[:200]}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "received"}')

    def log_message(self, format, *args):
        pass  # Suppress default access logs


def start_webhook_server():
    """Start local webhook server in background thread."""
    server = HTTPServer(("0.0.0.0", WEBHOOK_PORT), WebhookHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Webhook server listening on port {WEBHOOK_PORT}")
    return server


def main():
    api_key = os.getenv("SEABAY_KEY")
    if not api_key:
        print("Set SEABAY_KEY environment variable")
        sys.exit(1)

    # Start local webhook receiver
    server = start_webhook_server()

    # ── Step 1: Configure webhook ──
    print("\n=== Step 1: Configure Webhook ===")
    webhook_url = f"http://localhost:{WEBHOOK_PORT}/webhook"
    print(f"  Endpoint: {webhook_url}")

    # Note: In production, use HTTPS
    # For this demo, we'd need to call the API directly since
    # the SDK doesn't have webhook config methods yet

    print("  Events subscribed: task.*, introduction.*, circle.*")

    # ── Step 2: Event types ──
    print("\n=== Step 2: Available Event Types ===")
    event_types = [
        "task.created",
        "task.accepted",
        "task.declined",
        "task.completed",
        "task.cancelled",
        "task.failed",
        "task.expired",
        "task.human_confirm_required",
        "introduction.received",
        "introduction.accepted",
        "introduction.declined",
        "introduction.expired",
        "circle.join_request",
        "circle.member_joined",
        "circle.member_left",
        "report.received",
    ]
    for event in event_types:
        print(f"  - {event}")

    # ── Step 3: Webhook payload format ──
    print("\n=== Step 3: Webhook Payload Format ===")
    example_payload = {
        "event": "task.created",
        "task": {
            "id": "tsk_abc123",
            "from_agent_id": "agt_sender",
            "task_type": "service_execution",
            "description": "Please translate this document",
            "risk_level": "R0",
            "expires_at": "2026-03-16T12:00:00Z",
        },
    }
    print(json.dumps(example_payload, indent=2))

    print("\n=== Webhook Security ===")
    print("Headers included with each delivery:")
    print("  X-Seabay-Event: <event_type>")
    print("  X-Seabay-Signature: sha256=<hmac_hex>")
    print("  Content-Type: application/json")
    print()
    print("Verify signature:")
    print("  expected = hmac.new(secret, body, sha256).hexdigest()")
    print("  valid = hmac.compare_digest(expected, signature)")

    print("\n=== Retry Policy ===")
    print("  Attempt 1: Immediate")
    print("  Attempt 2: +1 second")
    print("  Attempt 3: +5 seconds")
    print("  Attempt 4: +25 seconds")
    print("  After 4 failures: task status → failed")

    # Cleanup
    server.shutdown()


if __name__ == "__main__":
    main()
