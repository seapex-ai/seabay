"""Seabay Translator Agent — AI-powered translation service.

Registers with Seabay API, polls for tasks, translates content using an LLM,
and returns results.

Usage:
    export SEABAY_API_URL=http://localhost:8000/v1
    export SEABAY_API_KEY=your_key    # If already registered
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
logger = logging.getLogger("translator")

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
        """Register a new agent and return credentials."""
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
        """Update agent profile with skills, languages, etc."""
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


# ── LLM Translation ──

def translate_text(text: str, source_lang: str = "auto", target_lang: str = "en") -> str:
    """Translate text using the configured LLM."""
    if not LLM_API_KEY:
        return f"[Translation unavailable — LLM_API_KEY not set]\nOriginal: {text}"

    system_prompt = (
        "You are a professional translator. Translate the given text accurately and naturally. "
        "Preserve formatting, tone, and meaning. If the source language is 'auto', detect it first."
    )

    user_prompt = f"Translate the following text from {source_lang} to {target_lang}:\n\n{text}"

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
                "max_tokens": 4096,
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error("LLM translation failed: %s", e)
        raise


def parse_translation_task(description: str) -> dict:
    """Extract translation parameters from a task description."""
    # Simple extraction — in production this would use the LLM
    params = {
        "text": description,
        "source_lang": "auto",
        "target_lang": "en",
    }

    lower = description.lower()

    # Try to detect target language from description
    lang_map = {
        "chinese": "zh", "mandarin": "zh", "中文": "zh",
        "japanese": "ja", "日本語": "ja",
        "korean": "ko", "한국어": "ko",
        "spanish": "es", "español": "es",
        "french": "fr", "français": "fr",
        "german": "de", "deutsch": "de",
        "portuguese": "pt", "português": "pt",
        "russian": "ru", "русский": "ru",
        "arabic": "ar", "العربية": "ar",
        "english": "en",
    }

    for lang_name, lang_code in lang_map.items():
        if f"to {lang_name}" in lower or f"into {lang_name}" in lower:
            params["target_lang"] = lang_code
            break

    for lang_name, lang_code in lang_map.items():
        if f"from {lang_name}" in lower:
            params["source_lang"] = lang_code
            break

    return params


# ── Main agent loop ──

def ensure_registered(config: dict) -> tuple[str, str]:
    """Ensure agent is registered. Returns (agent_id, api_key)."""
    state = load_state()

    if state.get("api_key") and SEABAY_API_KEY:
        return state.get("agent_id", ""), SEABAY_API_KEY

    if SEABAY_API_KEY:
        # Already have a key from env
        return state.get("agent_id", ""), SEABAY_API_KEY

    if state.get("api_key"):
        return state["agent_id"], state["api_key"]

    # Register new agent
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
        logger.info("API Key saved to .agent_state.json")
        return result["id"], result["api_key"]
    except Exception as e:
        logger.error("Registration failed: %s", e)
        sys.exit(1)


def process_task(agent: SeabayAgent, task: dict) -> None:
    """Process a single translation task."""
    task_id = task["id"]
    description = task.get("description", "")
    logger.info("Processing task %s: %s", task_id, description[:80])

    try:
        # Accept the task
        agent.accept_task(task_id)
        logger.info("Task %s accepted", task_id)

        # Parse and translate
        params = parse_translation_task(description)
        result = translate_text(
            text=params["text"],
            source_lang=params["source_lang"],
            target_lang=params["target_lang"],
        )

        # Complete the task
        agent.complete_task(task_id, notes=result)
        logger.info("Task %s completed", task_id)

    except Exception as e:
        logger.error("Task %s failed: %s", task_id, e)
        try:
            agent.fail_task(task_id, reason=str(e))
        except Exception:
            pass


def run_polling_loop(agent: SeabayAgent, config: dict) -> None:
    """Main polling loop — check inbox and process tasks."""
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
            else:
                logger.debug("No pending tasks")

        except httpx.ConnectError:
            logger.warning("Cannot connect to API. Retrying in %ds...", poll_interval * 2)
            time.sleep(poll_interval)
        except Exception as e:
            logger.error("Polling error: %s", e)

        time.sleep(poll_interval)


def main():
    config = load_config()
    logger.info("Seabay Translator Agent starting...")
    logger.info("API URL: %s", SEABAY_API_URL)

    # Ensure registered
    agent_id, api_key = ensure_registered(config)

    # Initialize API client
    agent = SeabayAgent(SEABAY_API_URL, api_key)

    # Update profile
    try:
        agent.update_profile(config)
        logger.info("Profile updated")
    except Exception as e:
        logger.warning("Profile update failed (non-fatal): %s", e)

    # Health check
    try:
        health = agent.health()
        logger.info("Server: %s v%s", health.get("service", "?"), health.get("version", "?"))
    except Exception:
        logger.warning("Health check failed — continuing anyway")

    # Run polling loop
    try:
        run_polling_loop(agent, config)
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
