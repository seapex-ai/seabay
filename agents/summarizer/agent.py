"""Seabay Summarizer Agent — AI-powered text summarization service.

Registers with Seabay API, polls for tasks, summarizes content using an LLM,
and returns results.

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
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("summarizer")

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
    """Minimal Seabay API client for agent operations."""

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


# ── LLM Summarization ──

SUMMARY_FORMATS = {
    "executive": (
        "Create a concise executive summary (2-3 paragraphs). "
        "Focus on key decisions, outcomes, and action items."
    ),
    "bullets": (
        "Summarize in clear bullet points (5-10 points). "
        "Each bullet should be a complete, self-contained statement."
    ),
    "key_points": (
        "Extract the 3-5 most important key points. "
        "For each point, provide a one-line summary and a brief explanation."
    ),
    "abstract": (
        "Write a brief abstract (150-200 words) suitable for academic or professional use."
    ),
    "default": (
        "Provide a clear, well-structured summary. "
        "Include the main topic, key points, conclusions, and any action items."
    ),
}


def summarize_text(text: str, format_type: str = "default", max_length: str = "medium") -> str:
    """Summarize text using the configured LLM."""
    if not LLM_API_KEY:
        return f"[Summarization unavailable — LLM_API_KEY not set]\nOriginal length: {len(text)} chars"

    length_hints = {
        "short": "Keep the summary very brief (under 100 words).",
        "medium": "Keep the summary moderate length (100-300 words).",
        "long": "Provide a detailed summary (300-500 words).",
    }

    format_instruction = SUMMARY_FORMATS.get(format_type, SUMMARY_FORMATS["default"])
    length_hint = length_hints.get(max_length, length_hints["medium"])

    system_prompt = (
        "You are an expert summarizer. Your summaries are clear, accurate, and well-organized. "
        "Preserve important details, numbers, names, and dates. "
        "Never fabricate information not present in the original text."
    )

    user_prompt = f"{format_instruction}\n{length_hint}\n\nText to summarize:\n\n{text}"

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
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 2048,
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error("LLM summarization failed: %s", e)
        raise


def parse_summary_task(description: str) -> dict:
    """Extract summarization parameters from a task description."""
    params = {
        "text": description,
        "format_type": "default",
        "max_length": "medium",
    }

    lower = description.lower()

    # Detect format preferences
    if "bullet" in lower or "bullet point" in lower:
        params["format_type"] = "bullets"
    elif "executive" in lower or "exec summary" in lower:
        params["format_type"] = "executive"
    elif "key point" in lower or "main point" in lower:
        params["format_type"] = "key_points"
    elif "abstract" in lower:
        params["format_type"] = "abstract"

    # Detect length preferences
    if "brief" in lower or "short" in lower or "quick" in lower:
        params["max_length"] = "short"
    elif "detailed" in lower or "comprehensive" in lower or "long" in lower:
        params["max_length"] = "long"

    return params


# ── Main agent loop ──

def ensure_registered(config: dict) -> tuple[str, str]:
    """Ensure agent is registered. Returns (agent_id, api_key)."""
    state = load_state()

    if SEABAY_API_KEY:
        return state.get("agent_id", ""), SEABAY_API_KEY

    if state.get("api_key"):
        return state["agent_id"], state["api_key"]

    logger.info("Registering agent '%s'...", config["slug"])
    try:
        result = SeabayAgent.register(SEABAY_API_URL, config)
        state = {
            "agent_id": result["id"],
            "api_key": result["api_key"],
            "slug": result["slug"],
        }
        save_state(state)
        logger.info("Registered! Agent ID: %s", result["id"])
        return result["id"], result["api_key"]
    except Exception as e:
        logger.error("Registration failed: %s", e)
        sys.exit(1)


def process_task(agent: SeabayAgent, task: dict) -> None:
    """Process a single summarization task."""
    task_id = task["id"]
    description = task.get("description", "")
    logger.info("Processing task %s: %s", task_id, description[:80])

    try:
        agent.accept_task(task_id)
        logger.info("Task %s accepted", task_id)

        params = parse_summary_task(description)
        result = summarize_text(
            text=params["text"],
            format_type=params["format_type"],
            max_length=params["max_length"],
        )

        agent.complete_task(task_id, notes=result)
        logger.info("Task %s completed", task_id)

    except Exception as e:
        logger.error("Task %s failed: %s", task_id, e)
        try:
            agent.fail_task(task_id, reason=str(e))
        except Exception:
            pass


def run_polling_loop(agent: SeabayAgent, config: dict) -> None:
    """Main polling loop."""
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
    logger.info("Seabay Summarizer Agent starting...")

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
