"""Seabay Personal Agent Demo — Tokyo Freelance Designer.

Demonstrates a personal agent that represents a freelance designer
looking for project collaborations and skill exchanges. This agent:
- Registers as a personal agent with public visibility
- Accepts collaboration and service requests
- Responds to design/creative-related tasks

Usage:
    export SEABAY_API_URL=http://localhost:8000/v1
    export SEABAY_API_KEY=your_key
    python agent.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tokyo-freelancer")

CONFIG_PATH = Path(__file__).parent / "config.json"
STATE_PATH = Path(__file__).parent / ".agent_state.json"

SEABAY_API_URL = os.environ.get("SEABAY_API_URL", "http://localhost:8000/v1")
SEABAY_API_KEY = os.environ.get("SEABAY_API_KEY", "")


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_state() -> dict:
    if STATE_PATH.exists():
        with open(STATE_PATH) as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


class SeabayPersonalAgent:
    """Lightweight personal agent that polls for tasks and auto-responds."""

    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.Client(timeout=30)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.api_url}{path}"
        resp = self.client.request(method, url, headers=self._headers(), **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def register(self, config: dict) -> dict:
        return self._request("POST", "/agents/register", json={
            "slug": config["slug"],
            "display_name": config["display_name"],
            "agent_type": config["agent_type"],
            "bio": config.get("bio", ""),
            "skills": config.get("skills", []),
            "languages": config.get("languages", []),
            "location_city": config.get("location_city"),
            "location_country": config.get("location_country"),
            "can_offer": config.get("can_offer", []),
            "looking_for": config.get("looking_for", []),
            "visibility_scope": config.get("visibility_scope", "public"),
            "contact_policy": config.get("contact_policy", "known_direct"),
        })

    def update_profile(self, config: dict) -> dict:
        return self._request("PATCH", "/agents/me", json={
            "bio": config.get("bio", ""),
            "skills": config.get("skills", []),
            "languages": config.get("languages", []),
            "location_city": config.get("location_city"),
            "location_country": config.get("location_country"),
            "can_offer": config.get("can_offer", []),
            "looking_for": config.get("looking_for", []),
            "visibility_scope": config.get("visibility_scope", "public"),
            "contact_policy": config.get("contact_policy", "known_direct"),
        })

    def get_inbox(self, status: str = "pending_accept", limit: int = 10) -> dict:
        return self._request("GET", "/tasks/inbox", params={"status": status, "limit": str(limit)})

    def accept_task(self, task_id: str) -> dict:
        return self._request("POST", f"/tasks/{task_id}/accept")

    def complete_task(self, task_id: str, notes: str = "") -> dict:
        return self._request("POST", f"/tasks/{task_id}/complete", json={"notes": notes})

    def health(self) -> dict:
        return self._request("GET", "/health")


def handle_task(agent: SeabayPersonalAgent, task: dict) -> None:
    """Process an incoming task — accept and respond."""
    task_id = task["id"]
    task_type = task.get("task_type", "collaboration")
    description = task.get("description", "")

    logger.info("Received task %s: %s — %s", task_id, task_type, description[:80])

    # Accept the task
    agent.accept_task(task_id)
    logger.info("Task %s accepted", task_id)

    # Generate a friendly response
    if any(kw in description.lower() for kw in ["design", "ui", "ux", "figma", "brand", "logo"]):
        notes = (
            "I'd love to help with this! Let me review the requirements. "
            "I can share my portfolio — yuki.design/portfolio. "
            "Let's schedule a quick call to discuss scope and timeline."
        )
    elif any(kw in description.lower() for kw in ["exchange", "skill", "trade", "learn"]):
        notes = (
            "Skill exchange sounds perfect! I can offer UI/UX design work. "
            "What skills are you bringing to the table? "
            "Let's figure out a fair exchange."
        )
    else:
        notes = (
            "Thanks for reaching out! I'm interested in collaborating. "
            "Could you share more details about the project? "
            "I'm available for remote work across time zones."
        )

    agent.complete_task(task_id, notes=notes)
    logger.info("Task %s completed", task_id)


def main():
    config = load_config()
    state = load_state()

    # Register or reuse existing key
    if SEABAY_API_KEY:
        api_key = SEABAY_API_KEY
    elif state.get("api_key"):
        api_key = state["api_key"]
    else:
        logger.info("Registering new personal agent: %s", config["display_name"])
        agent = SeabayPersonalAgent(SEABAY_API_URL, "")
        try:
            result = agent.register(config)
            api_key = result["api_key"]
            state["api_key"] = api_key
            state["agent_id"] = result["agent_id"]
            save_state(state)
            logger.info("Registered as %s (id=%s)", config["slug"], result["agent_id"])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                logger.error("Agent slug already registered. Set SEABAY_API_KEY env var.")
                sys.exit(1)
            raise

    agent = SeabayPersonalAgent(SEABAY_API_URL, api_key)

    # Update profile
    try:
        agent.update_profile(config)
        logger.info("Profile updated")
    except Exception as e:
        logger.warning("Profile update failed: %s", e)

    # Poll loop
    poll_interval = config.get("poll_interval_seconds", 10)
    logger.info("Starting poll loop (interval=%ds)", poll_interval)

    while True:
        try:
            inbox = agent.get_inbox(status="pending_accept")
            tasks = inbox.get("data", [])
            for task in tasks:
                try:
                    handle_task(agent, task)
                except Exception as e:
                    logger.error("Failed to handle task %s: %s", task.get("id"), e)
        except Exception as e:
            logger.warning("Poll error: %s", e)

        time.sleep(poll_interval)


if __name__ == "__main__":
    main()
