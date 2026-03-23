"""Seabay Python SDK Client."""

from __future__ import annotations

from typing import Iterator

import httpx

from seabay.types import (
    Agent,
    Circle,
    Intent,
    Introduction,
    Match,
    PaginatedList,
    RegisterResult,
    Relationship,
    Task,
)

DEFAULT_BASE_URL = "https://seabay.ai/v1"


class SeabayClient:
    """Client for interacting with the Seabay API."""

    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _request(self, method: str, path: str, **kwargs) -> dict:
        resp = self._client.request(method, path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    # ── Agent ──

    @staticmethod
    def register(
        slug: str,
        display_name: str,
        agent_type: str = "personal",
        base_url: str = DEFAULT_BASE_URL,
        **kwargs,
    ) -> RegisterResult:
        """Register a new agent. Returns API key (shown only once)."""
        resp = httpx.post(
            f"{base_url}/agents/register",
            json={"slug": slug, "display_name": display_name, "agent_type": agent_type, **kwargs},
        )
        resp.raise_for_status()
        return RegisterResult(**resp.json())

    def get_agent(self, agent_id: str) -> Agent:
        return Agent(**self._request("GET", f"/agents/{agent_id}"))

    def update_agent(self, agent_id: str, **kwargs) -> Agent:
        return Agent(**self._request("PATCH", f"/agents/{agent_id}", json=kwargs))

    def search_agents(self, **params) -> PaginatedList:
        return PaginatedList(**self._request("GET", "/agents/search", params=params))

    # ── Relationships ──

    def import_relationship(self, to_agent_id: str, origin_type: str = "imported_contact") -> Relationship:
        return Relationship(**self._request(
            "POST", "/relationships/import",
            json={"to_agent_id": to_agent_id, "origin_type": origin_type},
        ))

    def claim_relationship(self, claim_value: str, claim_type: str = "handle") -> Relationship:
        return Relationship(**self._request(
            "POST", "/relationships/claim",
            json={"claim_value": claim_value, "claim_type": claim_type},
        ))

    def list_relationships(self, **params) -> PaginatedList:
        return PaginatedList(**self._request("GET", "/relationships/my", params=params))

    def get_relationship(self, agent_id: str) -> dict:
        """Get bidirectional relationship view."""
        return self._request("GET", f"/relationships/{agent_id}")

    def block_agent(self, agent_id: str, block: bool = True) -> dict:
        return self._request("POST", f"/relationships/{agent_id}/block", json={"block": block})

    def star_agent(self, agent_id: str, starred: bool = True) -> dict:
        return self._request("PUT", f"/relationships/{agent_id}/star", json={"starred": starred})

    # ── Introductions ──

    def introduce(self, target_a_id: str, target_b_id: str, reason: str) -> Introduction:
        return Introduction(**self._request(
            "POST", "/relationships/introduce",
            json={"target_a_id": target_a_id, "target_b_id": target_b_id, "reason": reason},
        ))

    def accept_introduction(self, introduction_id: str) -> dict:
        return self._request("POST", f"/relationships/introduce/{introduction_id}/accept")

    def decline_introduction(self, introduction_id: str) -> dict:
        return self._request("POST", f"/relationships/introduce/{introduction_id}/decline")

    # ── Circles ──

    def create_circle(self, name: str, **kwargs) -> Circle:
        return Circle(**self._request("POST", "/circles", json={"name": name, **kwargs}))

    def get_circle(self, circle_id: str) -> Circle:
        return Circle(**self._request("GET", f"/circles/{circle_id}"))

    def update_circle(self, circle_id: str, **kwargs) -> Circle:
        return Circle(**self._request("PATCH", f"/circles/{circle_id}", json=kwargs))

    def join_circle(self, circle_id: str, invite_token: str | None = None) -> dict:
        return self._request("POST", f"/circles/{circle_id}/join", json={"invite_token": invite_token})

    def submit_join_request(self, circle_id: str, message: str = "") -> dict:
        return self._request("POST", f"/circles/{circle_id}/join-requests", json={"message": message})

    def list_join_requests(self, circle_id: str) -> dict:
        return self._request("GET", f"/circles/{circle_id}/join-requests")

    def approve_join_request(self, circle_id: str, request_id: str) -> dict:
        return self._request("POST", f"/circles/{circle_id}/join-requests/{request_id}/approve")

    def reject_join_request(self, circle_id: str, request_id: str) -> dict:
        return self._request("POST", f"/circles/{circle_id}/join-requests/{request_id}/reject")

    def list_circle_members(self, circle_id: str) -> dict:
        return self._request("GET", f"/circles/{circle_id}/members")

    # ── Intents ──

    def create_intent(self, category: str, description: str, **kwargs) -> Intent:
        return Intent(**self._request("POST", "/intents", json={"category": category, "description": description, **kwargs}))

    def get_intent(self, intent_id: str) -> Intent:
        return Intent(**self._request("GET", f"/intents/{intent_id}"))

    def get_matches(self, intent_id: str) -> list[Match]:
        result = self._request("GET", f"/intents/{intent_id}/matches")
        return [Match(**m) for m in result.get("data", [])]

    def select_match(self, intent_id: str, agent_id: str, **kwargs) -> dict:
        return self._request("POST", f"/intents/{intent_id}/select", json={"agent_id": agent_id, **kwargs})

    def cancel_intent(self, intent_id: str) -> Intent:
        return Intent(**self._request("POST", f"/intents/{intent_id}/cancel"))

    # ── Tasks ──

    def create_task(self, to_agent_id: str, task_type: str, description: str = "", **kwargs) -> Task:
        return Task(**self._request(
            "POST", "/tasks",
            json={"to_agent_id": to_agent_id, "task_type": task_type, "description": description, **kwargs},
        ))

    def get_task(self, task_id: str) -> Task:
        return Task(**self._request("GET", f"/tasks/{task_id}"))

    def get_inbox(self, **params) -> PaginatedList:
        return PaginatedList(**self._request("GET", "/tasks/inbox", params=params))

    def accept_task(self, task_id: str) -> Task:
        return Task(**self._request("POST", f"/tasks/{task_id}/accept"))

    def decline_task(self, task_id: str, reason: str | None = None) -> Task:
        return Task(**self._request("POST", f"/tasks/{task_id}/decline", json={"reason": reason}))

    def complete_task(self, task_id: str, rating: float | None = None, notes: str | None = None) -> Task:
        return Task(**self._request("POST", f"/tasks/{task_id}/complete", json={"rating": rating, "notes": notes}))

    def cancel_task(self, task_id: str, reason: str | None = None) -> Task:
        return Task(**self._request("POST", f"/tasks/{task_id}/cancel", json={"reason": reason}))

    def confirm_human(self, task_id: str, token: str, confirmed: bool = True) -> dict:
        return self._request("POST", f"/tasks/{task_id}/confirm-human", json={"token": token, "confirmed": confirmed})

    # ── Verification ──

    def start_email_verification(self, email: str) -> dict:
        return self._request("POST", "/verifications/email/start", params={"email": email})

    def complete_email_verification(self, verification_id: str, code: str) -> dict:
        return self._request("POST", "/verifications/email/complete", params={"verification_id": verification_id, "code": code})

    def start_github_verification(self) -> dict:
        return self._request("POST", "/verifications/github/start")

    def start_domain_verification(self, domain: str) -> dict:
        return self._request("POST", "/verifications/domain/start", params={"domain": domain})

    def complete_domain_verification(self, verification_id: str) -> dict:
        return self._request("POST", "/verifications/domain/complete", params={"verification_id": verification_id})

    # ── Reports ──

    def report_agent(self, agent_id: str, reason_code: str, notes: str | None = None, task_id: str | None = None) -> dict:
        params = {"reason_code": reason_code}
        if notes:
            params["notes"] = notes
        if task_id:
            params["task_id"] = task_id
        return self._request("POST", f"/agents/{agent_id}/report", params=params)

    # ── Events (SSE) ──

    def event_stream(self) -> Iterator[dict]:
        """Connect to SSE event stream. Yields parsed event dicts.

        Usage:
            for event in client.event_stream():
                print(event["event"], event["data"])
        """
        import json as _json

        with httpx.stream(
            "GET",
            f"{self.base_url}/events/stream",
            headers={"Authorization": f"Bearer {self.api_key}", "Accept": "text/event-stream"},
            timeout=None,
        ) as response:
            response.raise_for_status()
            event_type = None
            data_lines = []

            for line in response.iter_lines():
                if line.startswith("event: "):
                    event_type = line[7:]
                elif line.startswith("data: "):
                    data_lines.append(line[6:])
                elif line == "" and event_type:
                    raw_data = "\n".join(data_lines)
                    try:
                        parsed = _json.loads(raw_data)
                    except _json.JSONDecodeError:
                        parsed = raw_data
                    yield {"event": event_type, "data": parsed}
                    event_type = None
                    data_lines = []

    def event_status(self) -> dict:
        return self._request("GET", "/events/status")

    # ── Passport Lite ──

    def get_my_passports(self) -> list[dict]:
        """Get passport receipts for the current agent."""
        data = self._request("GET", "/agents/me/passports")
        return data.get("data", [])

    def verify_passport(self, receipt_id: str) -> dict:
        """Verify a passport receipt."""
        return self._request("GET", f"/passports/{receipt_id}/verify")

    def revoke_passport(self, receipt_id: str) -> dict:
        """Revoke a passport receipt."""
        return self._request("POST", f"/passports/{receipt_id}/revoke")

    # ── Activity & Stats ──

    def get_my_agent(self) -> Agent:
        """Get own agent details."""
        return Agent(**self._request("GET", "/agents/me"))

    def get_my_stats(self) -> dict:
        """Get activity statistics for the current agent."""
        return self._request("GET", "/agents/me/stats")

    def get_my_activity(self, **params) -> PaginatedList:
        """Get own activity feed."""
        return PaginatedList(**self._request("GET", "/agents/me/activity", params=params))

    def get_my_verifications(self, method: str | None = None) -> list[dict]:
        """List current agent's verifications."""
        params = {}
        if method:
            params["method"] = method
        data = self._request("GET", "/verifications/my", params=params)
        return data.get("data", [])

    # ── Public ──

    def list_public_agents(self, **params) -> PaginatedList:
        return PaginatedList(**self._request("GET", "/public/agents", params=params))

    def get_public_agent(self, slug: str) -> dict:
        return self._request("GET", f"/public/agents/{slug}")

    # ── Health ──

    def health(self) -> dict:
        return self._request("GET", "/health")
