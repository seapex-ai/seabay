"""Seabay Scheduler Agent — AI scheduling and calendar coordination service.

Registers with Seabay API, polls for tasks, processes scheduling requests
using an LLM, and returns structured scheduling suggestions.

Usage:
    export SEABAY_API_URL=http://localhost:8000/v1
    export SEABAY_API_KEY=your_key
    export LLM_API_KEY=your_openai_key
    python agent.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("scheduler")

# ── Configuration ──

CONFIG_PATH = Path(__file__).parent / "config.json"
STATE_PATH = Path(__file__).parent / ".agent_state.json"

SEABAY_API_URL = os.environ.get("SEABAY_API_URL", "http://localhost:8000/v1")
SEABAY_API_KEY = os.environ.get("SEABAY_API_KEY", "")
LLM_API_URL = os.environ.get("LLM_API_URL", "https://api.openai.com/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o")


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


# ── Seabay API client ──

class SeabayAgent:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.Client(
            base_url=self.api_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=30.0,
        )

    def _request(self, method: str, path: str, **kwargs) -> dict:
        resp = self._client.request(method, path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def register(api_url: str, config: dict) -> dict:
        resp = httpx.post(
            f"{api_url}/agents/register",
            json={
                "slug": config["slug"],
                "display_name": config["display_name"],
                "agent_type": config["agent_type"],
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def update_profile(self, config: dict) -> dict:
        return self._request("PATCH", "/agents/me", json={
            "bio": config.get("bio", ""),
            "skills": config.get("skills", []),
            "languages": config.get("languages", []),
            "location_city": config.get("location_city"),
            "location_country": config.get("location_country"),
            "can_offer": config.get("can_offer", []),
            "visibility_scope": config.get("visibility_scope", "public"),
            "contact_policy": config.get("contact_policy", "public_service_only"),
        })

    def get_inbox(self, status: str = "pending_accept", limit: int = 10) -> dict:
        return self._request("GET", "/tasks/inbox", params={"status": status, "limit": str(limit)})

    def accept_task(self, task_id: str) -> dict:
        return self._request("POST", f"/tasks/{task_id}/accept")

    def complete_task(self, task_id: str, notes: str = "", rating: float | None = None) -> dict:
        body: dict = {"notes": notes}
        if rating is not None:
            body["rating"] = rating
        return self._request("POST", f"/tasks/{task_id}/complete", json=body)

    def fail_task(self, task_id: str, reason: str = "") -> dict:
        return self._request("POST", f"/tasks/{task_id}/cancel", json={"reason": reason})

    def health(self) -> dict:
        return self._request("GET", "/health")


# ── LLM Scheduling ──

def process_scheduling_request(description: str) -> str:
    """Process a scheduling request using the LLM."""
    if not LLM_API_KEY:
        return "[Scheduling unavailable — LLM_API_KEY not set]"

    now = datetime.now(timezone.utc).isoformat()

    system_prompt = f"""You are a professional scheduling assistant. Current UTC time: {now}

Your capabilities:
1. Suggest optimal meeting times across time zones
2. Analyze schedule conflicts
3. Create event descriptions and agendas
4. Convert between time zones
5. Suggest recurring meeting patterns

When suggesting times:
- Always include the time zone
- Suggest 2-3 options when possible
- Consider common working hours (9 AM - 6 PM in each participant's zone)
- Note any potential conflicts or considerations

Format your response clearly with structured time slots and any relevant notes."""

    try:
        resp = httpx.post(
            f"{LLM_API_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": description},
                ],
                "temperature": 0.4,
                "max_tokens": 2048,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error("LLM scheduling failed: %s", e)
        raise


# ── Main agent loop ──

def ensure_registered(config: dict) -> tuple[str, str]:
    state = load_state()
    if SEABAY_API_KEY:
        return state.get("agent_id", ""), SEABAY_API_KEY
    if state.get("api_key"):
        return state["agent_id"], state["api_key"]

    logger.info("Registering agent '%s'...", config["slug"])
    try:
        result = SeabayAgent.register(SEABAY_API_URL, config)
        state = {"agent_id": result["id"], "api_key": result["api_key"], "slug": result["slug"]}
        save_state(state)
        logger.info("Registered! Agent ID: %s", result["id"])
        return result["id"], result["api_key"]
    except Exception as e:
        logger.error("Registration failed: %s", e)
        sys.exit(1)


def process_task(agent: SeabayAgent, task: dict) -> None:
    task_id = task["id"]
    description = task.get("description", "")
    logger.info("Processing task %s: %s", task_id, description[:80])

    try:
        agent.accept_task(task_id)
        logger.info("Task %s accepted", task_id)

        result = process_scheduling_request(description)

        agent.complete_task(task_id, notes=result)
        logger.info("Task %s completed", task_id)

    except Exception as e:
        logger.error("Task %s failed: %s", task_id, e)
        try:
            agent.fail_task(task_id, reason=str(e))
        except Exception:
            pass


def run_polling_loop(agent: SeabayAgent, config: dict) -> None:
    poll_interval = config.get("poll_interval_seconds", 5)
    logger.info("Starting polling loop (interval: %ds)...", poll_interval)

    while True:
        try:
            inbox = agent.get_inbox(status="pending_accept")
            tasks = inbox.get("data", [])
            if tasks:
                logger.info("Found %d pending task(s)", len(tasks))
                for task in tasks:
                    process_task(agent, task)
        except httpx.ConnectError:
            logger.warning("Cannot connect to API. Retrying...")
            time.sleep(poll_interval)
        except Exception as e:
            logger.error("Polling error: %s", e)

        time.sleep(poll_interval)


def main():
    config = load_config()
    logger.info("Seabay Scheduler Agent starting...")

    agent_id, api_key = ensure_registered(config)
    agent = SeabayAgent(SEABAY_API_URL, api_key)

    try:
        agent.update_profile(config)
        logger.info("Profile updated")
    except Exception as e:
        logger.warning("Profile update failed: %s", e)

    try:
        health = agent.health()
        logger.info("Server: %s v%s", health.get("service", "?"), health.get("version", "?"))
    except Exception:
        logger.warning("Health check failed")

    try:
        run_polling_loop(agent, config)
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
